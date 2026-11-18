"""纯模型基线 llm_judge：只用假 transport，不联网、不需要密钥、不读取 .env。"""
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from confidence_07a.eval.baselines import llm_judge as lj
from confidence_07a.eval.runner import load_results_dir, records_to_runs

from ._sc_support import FIXTURES, fixture_logs

ENV = {lj.ENV_BASE_URL: "http://127.0.0.1:9/v1", lj.ENV_API_KEY: "test-key-not-real", lj.ENV_MODEL: "fake-model"}

MODEL_JSON = {
    "goals": [{"id": "G1", "text": "行车检验过了吗"}, {"id": "G2", "text": "可以吊吗"}],
    "claims": [
        {"id": "C1", "text": "检验结果为合格", "status": "SUPPORT", "expression": "DEFINITE", "goal_ids": ["G1"],
         "evidence": [{"event_id": "c1", "json_path": "trace[c1].result.inspection_result"}], "reason": "inspection_result=合格"},
        {"id": "C2", "text": "今天吊装18吨设备没有问题", "status": "REFUTE", "expression": "DEFINITE", "goal_ids": ["G2"],
         "evidence": [{"event_id": "c1", "json_path": "trace[c1].result.restriction"},
                      {"event_id": "c9", "json_path": "trace[c9].result.made_up"}], "reason": "限重15吨"},
        {"id": "C3", "text": "可以正常作业", "status": "PROBABLY_OK", "expression": "weird", "goal_ids": ["G9"], "evidence": []},
    ],
    "gaps": [{"id": "GAP1", "type": "MISSING_EVIDENCE", "affects": ["C3"], "criticality": "HIGH", "description": "许可待审批"}],
    "actions": [{"id": "A1", "gap_ids": ["GAP1"], "tool": "safety.permit_check", "arguments": {"plan_id": "LP-2026-1114-01"},
                 "pending_arguments": {}, "success_criterion": "permit_status=已批准"}],
}


class FakeTransport:
    def __init__(self, status=200, content=None, raw=None):
        self.calls = []
        self.status = status
        self.content = json.dumps(MODEL_JSON, ensure_ascii=False) if content is None else content
        self.raw = raw

    def __call__(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": headers, "body": json.loads(body.decode("utf-8")), "timeout": timeout})
        if self.raw is not None:
            return self.status, self.raw
        payload = {"choices": [{"message": {"content": self.content}}],
                   "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}
        return self.status, json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _no_network(*a, **k):
    raise AssertionError("不应发起网络请求")


class TestConfig(unittest.TestCase):
    def test_from_env_mapping_only(self):
        cfg = lj.LLMConfig.from_env(ENV)
        self.assertEqual(cfg.model, "fake-model")
        self.assertEqual(cfg.endpoint(), "http://127.0.0.1:9/v1/chat/completions")
        self.assertNotIn("api_key", cfg.public())
        self.assertNotIn("test-key-not-real", json.dumps(cfg.public()))

    def test_missing_env_raises_without_leaking(self):
        with self.assertRaises(RuntimeError) as cm:
            lj.LLMConfig.from_env({lj.ENV_API_KEY: "secret-xyz"})
        self.assertIn(lj.ENV_BASE_URL, str(cm.exception))
        self.assertNotIn("secret-xyz", str(cm.exception))


class TestPromptAndParse(unittest.TestCase):
    def setUp(self):
        self.rec = fixture_logs()["IND-053-r1"]

    def test_prompt_contains_only_log_fields(self):
        msgs = lj.build_messages(self.rec)
        self.assertEqual([m["role"] for m in msgs], ["system", "user"])
        self.assertIn("CRANE-02", msgs[1]["content"])
        self.assertIn(self.rec["ai_answer"], msgs[1]["content"])
        for banned in ("gold", "案例说明", "evidence_status"):
            self.assertNotIn(banned, msgs[1]["content"])

    def test_parse_json_content_tolerates_fences(self):
        self.assertEqual(lj.parse_json_content("```json\n{\"a\": 1}\n```"), {"a": 1})
        self.assertEqual(lj.parse_json_content("好的：{\"a\": [1]} 以上"), {"a": [1]})
        with self.assertRaises(ValueError):
            lj.parse_json_content("")
        with self.assertRaises(ValueError):
            lj.parse_json_content("没有 JSON")

    def test_parsed_to_run_view(self):
        run = lj.parsed_to_run_view(MODEL_JSON, self.rec)
        self.assertEqual(run.run_id, "IND-053-r1")
        self.assertEqual(run.source["method"], "llm_only")
        c1, c2, c3 = run.claims
        self.assertEqual(c1.status, "SUPPORT")
        self.assertEqual(len(c1.evidence_ids), 1)
        self.assertEqual(run.evidence[c1.evidence_ids[0]].value, "合格")
        self.assertEqual(c2.status, "REFUTE")
        self.assertEqual(len(c2.evidence_ids), 1)  # c9 编造的定位被丢弃
        self.assertEqual(run.build_risks["invalid_locators"], ["C2:trace[c9].result.made_up"])
        self.assertEqual(c3.status, "UNKNOWN")  # 非法状态 -> UNKNOWN 并记录
        self.assertIsNone(c3.expression)
        self.assertEqual(c3.related_goals, [])
        self.assertEqual(c3.gap_ids, ["GAP1"])
        self.assertEqual(run.actions[0].target_claims, ["C3"])  # 由 gap 推出
        self.assertTrue(any("非法状态" in n for n in run.notes))


class TestCallAndJudge(unittest.TestCase):
    def setUp(self):
        self.rec = fixture_logs()["IND-053-r1"]
        self.cfg = lj.LLMConfig.from_env(ENV)

    def test_call_chat_request_and_usage(self):
        t = FakeTransport()
        res = lj.call_chat(self.cfg, lj.build_messages(self.rec), t)
        self.assertIsNone(res["error"])
        self.assertEqual(res["usage"]["total_tokens"], 150)
        self.assertIsInstance(res["latency_seconds"], float)
        call = t.calls[0]
        self.assertEqual(call["headers"]["Authorization"], "Bearer test-key-not-real")
        self.assertEqual(call["body"]["model"], "fake-model")
        self.assertEqual(call["body"]["temperature"], 0.0)
        self.assertEqual(call["body"]["response_format"], {"type": "json_object"})

    def test_http_error_and_bad_body(self):
        res = lj.call_chat(self.cfg, [], FakeTransport(status=401, raw=b'{"error": {"message": "bad key"}}'))
        self.assertIn("HTTP 401", res["error"])
        res = lj.call_chat(self.cfg, [], FakeTransport(raw=b"<html>"))
        self.assertIn("不是 JSON", res["error"])

    def test_judge_record_and_converter(self):
        rec = lj.judge_record(self.rec, self.cfg, FakeTransport())
        self.assertTrue(rec["passed"])
        self.assertEqual(rec["llm_call_count"], 1)
        self.assertEqual(rec["usage"]["prompt_tokens"], 100)
        self.assertNotIn("test-key-not-real", json.dumps(rec, ensure_ascii=False))
        conv = records_to_runs({"IND-053-r1": rec}, "llm_only", {"IND-053-r1": self.rec}, converter=lj.converter)
        run = conv["runs"][0]
        self.assertEqual(run.source["llm_call_count"], 1)
        self.assertEqual(len(run.claims), 3)

    def test_judge_record_parse_failure(self):
        rec = lj.judge_record(self.rec, self.cfg, FakeTransport(content="抱歉，我无法回答"))
        self.assertFalse(rec["passed"])
        self.assertEqual(rec["error_type"], "LLMOutputParseError")


class TestMain(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="07a_lj_"))
        self.log = FIXTURES / "logs_5cases.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, argv, env=None, transport=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = lj.main(argv, env=env, transport=transport)
        return rc, out.getvalue(), err.getvalue()

    def test_dry_run_needs_no_key_and_no_network(self):
        rc, out, _ = self._run(["--log", str(self.log), "--run-ids", "IND-053-r1", "--dry-run"], env={}, transport=_no_network)
        self.assertEqual(rc, 0)
        self.assertIn("### system", out)
        self.assertIn("[dry-run]", out)

    def test_missing_env_returns_2(self):
        rc, _, err = self._run(["--log", str(self.log), "--all", "--out", str(self.tmp / "o")], env={}, transport=_no_network)
        self.assertEqual(rc, 2)
        self.assertIn(lj.ENV_API_KEY, err)

    def test_full_run_with_fake_transport(self):
        t = FakeTransport()
        out = self.tmp / "llm_only"
        rc, stdout, _ = self._run(["--log", str(self.log), "--run-ids", "IND-053-r1,IND-043-r1", "--out", str(out)],
                                  env=ENV, transport=t)
        self.assertEqual(rc, 0)
        self.assertEqual(len(t.calls), 2)
        files = sorted(out.glob("*.json"))
        self.assertEqual(len(files), 2)
        for p in files:
            self.assertNotIn("test-key-not-real", p.read_text(encoding="utf-8"))
        loaded = load_results_dir(out)
        self.assertEqual(sorted(k for k in loaded if not k.startswith("_")), ["IND-043-r1", "IND-053-r1"])
        self.assertIn("token 合计", stdout)


if __name__ == "__main__":
    unittest.main()


class TestUrllibTransportNetworkError(unittest.TestCase):
    def test_connection_refused_becomes_error_record(self):
        from confidence_07a.eval.baselines import llm_judge as lj
        status, raw = lj.urllib_transport("http://127.0.0.1:9/chat/completions", {}, b"{}", 2.0)
        self.assertEqual(status, 0)
        self.assertIn("network error", raw.decode("utf-8"))
