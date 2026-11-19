import io
import json
import logging
import runpy
import subprocess
import sys
import tempfile
import threading
import traceback
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from user_sim import UserSimError, generate_question, to_log_record
from user_sim import client
from user_sim.catalog import REPO, load_scenarios
from user_sim.personas import PERSONA_IDS, PERSONAS
from user_sim.prompt import MODEL_OUTPUT_SCHEMA
from user_sim.server import _make_server

KEY = "sk-test-XXXX"
ENV = {"USER_SIM_API_KEY": KEY}
SCHEMA = json.loads((REPO / "user_sim/schemas/sim_question.v1.schema.json").read_text(encoding="utf-8"))


def _reply(out):
    content = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
    return 200, json.dumps({"choices": [{"message": {"content": content}}],
                            "provider": "Nebius", "usage": {"prompt_tokens": 18, "completion_tokens": 7}}
                           ).encode("utf-8")


def _valid(url, headers, body, timeout):
    data = json.loads(body)
    prompt = json.loads(data["messages"][1]["content"])
    card = prompt["场景卡"]
    entity = next((e["id"] for e in card["entities"]), "")
    pid = next(p for p in PERSONAS if PERSONAS[p]["label_zh"] == prompt["画像"])
    questions = {
        "expert": f"请调出{entity}今天早班交接时的原始记录，核对一下当前登记的状态。",
        "speculator": f"我怀疑{entity}上一班的记录还没更新，能帮忙调台账核实一下吗？",
        "reporter": "刚才交班的时候我看见有两张单子一直搁在那儿，你帮忙看看。",
        "novice": "我手里这张单子一直没动静，现在该怎么办呀？",
    }
    return _reply({"user_question": questions[pid], "intent": prompt["目标意图"],
                   "mentioned_entities": [entity] if entity and pid in ("expert", "speculator") else [],
                   "self_check": "只记日志的画像自检 " + KEY})


def _assert_schema(test, obj, rule):
    """只解释仓库 schema 实际用到的关键词，保持验收零依赖。"""
    if "$ref" in rule:
        _assert_schema(test, obj, SCHEMA["$defs"][rule["$ref"].rsplit("/", 1)[1]])
    if "if" in rule:
        selector = rule["if"]["properties"]
        matched = all(obj[k] == pred["const"] for k, pred in selector.items())
        _assert_schema(test, obj, rule["then" if matched else "else"])
    if "const" in rule:
        test.assertEqual(obj, rule["const"])
    if "enum" in rule:
        test.assertIn(obj, rule["enum"])
    if "type" in rule:
        names = {"string": (str,), "integer": (int,), "number": (float, int), "array": (list,),
                 "object": (dict,), "null": (type(None),)}
        types = rule["type"] if isinstance(rule["type"], list) else [rule["type"]]
        test.assertTrue(any(type(obj) in names[name] for name in types))
    if isinstance(obj, dict):
        props = rule.get("properties", {})
        test.assertLessEqual(set(rule.get("required", [])), set(obj))
        if rule.get("additionalProperties") is False:
            test.assertLessEqual(set(obj), set(props))
        for k in obj.keys() & props.keys():
            _assert_schema(test, obj[k], props[k])
    if "items" in rule:
        test.assertLessEqual(len(obj), rule.get("maxItems", len(obj)))
        for item in obj:
            _assert_schema(test, item, rule["items"])
    if isinstance(obj, str):
        test.assertGreaterEqual(len(obj), rule.get("minLength", 0))
        test.assertLessEqual(len(obj), rule.get("maxLength", len(obj)))
        if "pattern" in rule:
            test.assertRegex(obj, rule["pattern"])
        if rule.get("format") == "date-time":
            test.assertIsNotNone(datetime.fromisoformat(obj).tzinfo)
    if type(obj) in (int, float):
        test.assertGreaterEqual(obj, rule.get("minimum", obj))
        test.assertLessEqual(obj, rule.get("maximum", obj))


class ClientTests(unittest.TestCase):
    def test_request_defaults_and_headers(self):
        transport = Mock(return_value=_reply({}))
        client.chat_json([], schema=MODEL_OUTPUT_SCHEMA, seed=0, env=ENV, transport=transport)
        url, headers, body, timeout = transport.call_args.args
        self.assertEqual((url, timeout), (client.DEFAULT_BASE_URL, 30))
        self.assertEqual(headers["Authorization"], "Bearer " + KEY)
        self.assertEqual(headers["HTTP-Referer"], "https://github.com/forest1119/SYE6601-warehouse")
        self.assertEqual(headers["X-Title"], "SYE6601 user-sim")
        self.assertNotIn(KEY.encode("utf-8"), body)
        payload = json.loads(body)
        self.assertEqual(payload["provider"], {"quantizations": ["fp4"], "allow_fallbacks": True})
        self.assertEqual(payload["reasoning"], {"enabled": False})
        self.assertEqual(payload["model"], "qwen/qwen3.8-27b")
        self.assertEqual([payload[k] for k in ("temperature", "top_p", "max_tokens", "seed")], [0.9, 0.95, 600, 0])
        self.assertEqual(payload["response_format"], {"type": "json_schema", "json_schema": {
            "name": "sim_question", "strict": True, "schema": MODEL_OUTPUT_SCHEMA}})

    def test_request_overrides_and_key_priority(self):
        transport = Mock(return_value=_reply({}))
        env = {"OPENROUTER_API_KEY": KEY, "USER_SIM_BASE_URL": "https://example.invalid/chat",
               "USER_SIM_MODEL": "mock", "USER_SIM_QUANT": "fp8", "USER_SIM_REASONING": "low"}
        client.chat_json([], schema={}, transport=transport, env=env)
        url, headers, body, _ = transport.call_args.args
        self.assertEqual(url, env["USER_SIM_BASE_URL"])
        self.assertEqual(headers["Authorization"], "Bearer " + KEY)
        self.assertEqual(json.loads(body)["provider"]["quantizations"], ["fp8"])
        self.assertEqual(json.loads(body)["model"], "mock")
        self.assertEqual(json.loads(body)["reasoning"], {"effort": "low", "exclude": True})
        self.assertEqual(json.loads(body)["max_tokens"], 2000)
        custom = {"effort": "medium"}
        self.assertEqual(client.build_request([], schema={}, env=env, reasoning=custom)["reasoning"], custom)
        self.assertEqual(client.get_api_key({**ENV, "OPENROUTER_API_KEY": "unused"}), KEY)
        self.assertIsNone(client.get_api_key({}))

    def test_exception_redaction_including_traceback(self):
        def fault(*args):
            raise OSError("upstream echoed " + KEY)
        with self.assertRaises(UserSimError) as caught:
            client.chat_json([], schema={}, env=ENV, transport=fault)
        self.assertIn("***", str(caught.exception))
        self.assertNotIn(KEY, "".join(traceback.format_exception(caught.exception)))
        q = generate_question(env=ENV, transport=fault)
        self.assertNotIn(KEY, json.dumps(q))


class GenerationTests(unittest.TestCase):
    def test_success_schema_log_record_and_self_check(self):
        for domain in ("insurance", "industrial"):
            observed = Mock(side_effect=_valid)
            buf = io.StringIO()
            with self.assertLogs("user_sim.generator", logging.DEBUG) as logs, redirect_stdout(buf), redirect_stderr(buf):
                q = generate_question(domain, "expert", seed=4, env=ENV, transport=observed)
            _assert_schema(self, q, SCHEMA)
            self.assertEqual(q["generator"]["mode"], "llm")
            self.assertEqual(q["generator"]["provider"], "Nebius")
            self.assertEqual(q["generator"]["usage"], {"prompt_tokens": 18, "completion_tokens": 7})
            self.assertEqual(q["run_id"], q["case_id"] + "-r1")
            self.assertEqual(q["visible_context"]["received_at"][10:], q["created_at"][10:])
            card = next(c for c in load_scenarios() if c["scenario_id"] == q["scenario_id"])
            self.assertEqual(q["visible_context"], {**card["context"], "received_at": card["data_date"] + q["created_at"][10:]})
            record = to_log_record(q)
            self.assertEqual(record, {**{k: q[k] for k in ("case_id", "run_id", "user_question", "visible_context")},
                                      "trace": [], "ai_answer": ""})
            body = observed.call_args.args[2].decode("utf-8")
            prompt = json.loads(json.loads(body)["messages"][1]["content"])
            self.assertEqual(len(set(prompt["同领域语气示例"])), 2)
            refs = {c["style_ref"] for c in load_scenarios() if c["domain"] == domain}
            self.assertLessEqual(set(prompt["同领域语气示例"]), refs - {card["style_ref"]})
            self.assertNotIn("ai_answer", body)
            self.assertNotIn("只记日志", json.dumps(q, ensure_ascii=False))
            self.assertIn("只记日志", str(logs.output))
            self.assertNotIn(KEY, body + str(logs.output) + str(q) + buf.getvalue())

    def test_retry_uses_feedback_and_same_scenario(self):
        for first in ({"intent": "garbage"}, "这不是 JSON"):
            calls = []
            def retry(url, headers, body, timeout):
                calls.append(json.loads(json.loads(body)["messages"][1]["content"]))
                return _reply(first) if len(calls) == 1 else _valid(url, headers, body, timeout)
            q = generate_question("insurance", "novice", seed=7, env=ENV, transport=retry)
            self.assertEqual(q["generator"]["attempts"], 2)
            self.assertEqual(q["generator"]["mode"], "llm")
            self.assertEqual(calls[0]["场景卡"], calls[1]["场景卡"])
            self.assertTrue(calls[1]["改写要求"])
            self.assertNotIn("改写要求", calls[0])

    def test_network_and_validation_fallback(self):
        for env, fake, n, message in [
            ({}, Mock(), 0, "未配置密钥"),
            (ENV, Mock(return_value=(500, KEY.encode("utf-8"))), 1, "HTTP 500"),
            (ENV, Mock(side_effect=TimeoutError("timeout " + KEY)), 1, "TimeoutError"),
            (ENV, Mock(return_value=_reply({})), 2, "两次校验"),
        ]:
            with self.subTest(note=message):
                q = generate_question("insurance", "speculator", "decision", 17, env=env, transport=fake)
                _assert_schema(self, q, SCHEMA)
                self.assertEqual(q["intent"], "decision")
                self.assertEqual(q["persona"]["id"], "speculator")
                self.assertEqual(q["generator"]["mode"], "offline_fallback")
                self.assertIn(message, q["generator"]["note"])
                self.assertEqual(q["generator"]["attempts"], n)
                self.assertEqual(fake.call_count, n)
                self.assertNotIn(KEY, str(q))

    def test_seed_and_two_hundred_mock_generations(self):
        records = [generate_question("insurance", seed=i, env=ENV, transport=_valid) for i in range(200)]
        self.assertEqual({r["persona"]["id"] for r in records}, set(PERSONA_IDS))
        self.assertEqual({r["generator"]["mode"] for r in records}, {"llm"})
        again = generate_question("insurance", seed=77, env=ENV, transport=_valid)
        for k in ("user_question", "scenario_id", "persona", "intent", "grounding"):
            self.assertEqual(records[77][k], again[k])
        self.assertNotEqual(records[77]["case_id"], again["case_id"])

    def test_recent_five_and_output_isolation(self):
        recent = []
        for _ in range(16):
            q = generate_question("industrial", "expert", offline=True, env=ENV)
            self.assertNotIn(q["scenario_id"], recent[-5:])
            recent.append(q["scenario_id"])
            q["grounding"]["entities"].clear()
        q = generate_question("industrial", "expert", offline=True, env=ENV)
        self.assertTrue(q["grounding"]["entities"])


class InterfaceTests(unittest.TestCase):
    def test_demo_generates_once_and_exposes_copyable_log(self):
        from user_sim.ui import render_user_sim_button

        st = MagicMock()
        st.session_state = {}
        st.radio.return_value = "insurance"
        st.selectbox.return_value = "reporter"
        st.button.side_effect = [True, False]
        q = generate_question("insurance", "reporter", offline=True, env={})
        callback = Mock()
        with patch.dict(sys.modules, {"streamlit": st}), patch("user_sim.ui.generate_question", return_value=q) as gen:
            self.assertIs(render_user_sim_button(on_generate=callback), q)
            self.assertIs(st.session_state["user_sim_question"], q)
            with patch.object(sys, "path", list(sys.path)):
                runpy.run_path(str(REPO / "apps/user_sim_demo.py"))
        gen.assert_called_once_with(domain="insurance", persona="reporter")
        callback.assert_called_once_with(q)
        st.title.assert_called_once_with("用户模拟 Agent")
        st.caption.assert_any_call("离线备用题")
        self.assertEqual(json.loads(st.code.call_args.args[0]), to_log_record(q))

    def test_missing_streamlit_hint(self):
        from user_sim.ui import render_user_sim_button
        with patch.dict(sys.modules, {"streamlit": None}):
            with self.assertRaisesRegex(RuntimeError, "需要 Streamlit"):
                render_user_sim_button()
            with self.assertRaisesRegex(SystemExit, "需要 Streamlit"):
                runpy.run_path(str(REPO / "apps/user_sim_demo.py"))

    def test_cli_writes_utf8_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "子目录" / "questions.jsonl"
            subprocess.run([sys.executable, "-m", "user_sim", "--domain", "insurance", "--persona", "speculator",
                            "--seed", "7", "--n", "3", "--offline", "--out", str(path)], cwd=REPO, check=True)
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r["generator"]["seed"] for r in rows], [7, 8, 9])
        for q in rows:
            _assert_schema(self, q, SCHEMA)
            self.assertEqual(q["persona"]["id"], "speculator")
            self.assertEqual(q["domain"], "insurance")

    def test_http_local_random_port(self):
        with _make_server(0) as server:
            self.assertEqual(server.server_address[0], "127.0.0.1")
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
            thread.start()
            try:
                conn = HTTPConnection(*server.server_address, timeout=5)
                try:
                    conn.request("POST", "/generate", body=b'{"domain":"industrial","offline":true}')
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    _assert_schema(self, json.loads(response.read().decode("utf-8")), SCHEMA)
                    conn.request("POST", "/generate", body=b'{"env":{}}')
                    response = conn.getresponse()
                    self.assertEqual(response.status, 400)
                    response.read()
                finally:
                    conn.close()
            finally:
                server.shutdown()
                thread.join()

