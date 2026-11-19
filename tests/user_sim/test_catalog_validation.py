import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from user_sim._fallback import _build
from user_sim.catalog import DATA, POLICY_PATH, REPO, _logs, build_scenarios, load_scenarios
from user_sim.personas import PERSONA_IDS
from user_sim.validate import _answer_numbers, validate_output


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = {r["case_id"]: r for _, r in _logs(REPO)}
        cls.cards = build_scenarios()
        cls.by_case = {c["scenario_id"]: c for c in cls.cards}

    def test_catalog_matches_sources_and_committed_data(self):
        self.assertEqual(self.cards, load_scenarios())
        self.assertEqual(Counter(c["domain"] for c in self.cards), {"insurance": 60, "industrial": 60})
        self.assertEqual(set(self.rows), set(self.by_case))
        words = json.loads(POLICY_PATH.read_text(encoding="utf-8"))["high_risk"]["lexicon"]
        for card in self.cards:
            with self.subTest(card=card["scenario_id"]):
                self.assertEqual(set(card), {"scenario_id", "domain", "context", "entities", "topic",
                                             "intent_hints", "tools", "risk", "style_ref", "data_date"})
                self.assertEqual(card["data_date"], self.rows[card["scenario_id"]]["visible_context"]["received_at"][:10])
                row = self.rows[card["scenario_id"]]
                self.assertEqual(card["context"], {k: v for k, v in row["visible_context"].items()
                                                   if k != "received_at"})
                self.assertEqual(card["style_ref"], row["user_question"])
                self.assertRegex(card["topic"], r"^[\u4e00-\u9fff]{2,8}$")
                self.assertLessEqual(len(card["entities"]), 8)
                self.assertEqual(len({e["id"] for e in card["entities"]}), len(card["entities"]))
                high = any(w in " ".join([card["style_ref"], *card["tools"]]) for w in words)
                self.assertEqual(card["risk"], "high" if high else "normal")

    def test_dates_must_stay_in_data_period(self):
        from user_sim.validate import _date_errors
        self.assertEqual(_date_errors("HP-03今天上午的压力峰值是多少？", "2026-11-14"), [])
        self.assertEqual(_date_errors("11月13日B线产量多少？", "2026-11-14"), [])
        self.assertTrue(_date_errors("2023年10月15日的压力峰值是多少？", "2026-11-14"))
        self.assertTrue(_date_errors("3月15日的库存够不够？", "2026-11-14"))
        self.assertTrue(_date_errors("保单在2025-02-01的金额是多少？", "2026-11-17"))

    def test_entity_extraction_and_intents(self):
        for case, ident, kind in [("IND-053", "CRANE-02", "asset"), ("IND-043", "Line-D", "line"),
                                  ("INS-A03", "HC-260115-2201", "policy"), ("IND-001", "三号锅炉", "asset")]:
            entity, = [e for e in self.by_case[case]["entities"] if e["id"] == ident]
            self.assertEqual(entity["kind"], kind)
        self.assertEqual(self.by_case["IND-001"]["entities"][0]["label"], "三号锅炉")
        self.assertEqual(self.by_case["IND-053"]["topic"], "吊装放行")
        self.assertEqual(self.by_case["IND-043"]["intent_hints"], ["value"])
        self.assertNotIn("SZL-20", {e["id"] for e in self.by_case["IND-001"]["entities"]})
        self.assertNotIn("policy_id", self.by_case["INS-A07"]["context"])

    def test_optional_loopb_joins_only_related_source_rows(self):
        def rec(family, case, **lookup):
            return {"family": family, "lookup": lookup,
                    "provenance": {"observed_task_context": {"case_id": case}}}

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "databases/industrial/tools.json"
            path.parent.mkdir(parents=True)
            records = [rec("SOURCE", "IND-053", asset_tag="BR-901"),
                       rec("SOURCE", "IND-053", asset_id="SIM01-BR-902"),
                       rec("RESULT", "IND-053", asset_id="BR-903"),
                       rec("SOURCE", "IND-001", asset_id="BR-904")]
            records.append({
                "family": "SOURCE", "lookup": {"equipment_id": "BR-905"},
                "provenance": {"observed_task_context": self.rows["IND-053"]["visible_context"]},
            })
            path.write_text(json.dumps({"records": records}), encoding="utf-8")
            cards = {c["scenario_id"]: c for c in build_scenarios(loopb_root=Path(tmp))}
        ids = {e["id"] for e in cards["IND-053"]["entities"]}
        self.assertEqual(ids - {e["id"] for e in self.by_case["IND-053"]["entities"]}, {"BR-901", "BR-905"})

    def test_entire_fallback_bank(self):
        bank = json.loads((DATA / "fallback_questions.json").read_text(encoding="utf-8"))
        # 题库由真实模型生成（user_sim._regen_bank），不足时用模板 _build() 补齐
        self.assertTrue(all(q.get("source") in ("llm", "template") for q in bank))
        templates = {t["user_question"] for t in _build()}
        self.assertTrue(all(q["user_question"] in templates for q in bank if q["source"] == "template"))
        self.assertEqual(len({q["user_question"] for q in bank}), len(bank))
        counts = Counter((q["domain"], q["persona"]) for q in bank)
        self.assertTrue(all(counts[d, p] >= 6 for d in ("industrial", "insurance") for p in PERSONA_IDS))
        for q in bank:
            card = self.by_case[q["scenario_id"]]
            with self.subTest(case=q["scenario_id"], persona=q["persona"]):
                self.assertIs(q["reviewed"], False)
                self.assertEqual(q["domain"], card["domain"])
                if q["persona"] in ("expert", "speculator"):
                    self.assertTrue(any(e[k] and e[k] in q["user_question"]
                                        for e in card["entities"] for k in ("label", "id")))
                out = {k: q[k] for k in ("intent", "self_check", "user_question", "mentioned_entities")}
                refs = [c["style_ref"] for c in self.cards if c["domain"] == card["domain"]]
                self.assertEqual(validate_output(out, card, q["persona"], refs,
                                                 _answer_numbers(self.rows[q["scenario_id"]])), [])


class ValidationTests(unittest.TestCase):
    card = {"entities": [{"id": "BLR-03", "label": "三号锅炉", "kind": "asset"}],
            "tools": ["ops.alarm_history"]}

    def check(self, question, persona="novice", refs=(), nums=(), **fields):
        out = {"user_question": question, "intent": "status", "self_check": "", "mentioned_entities": []}
        out.update(fields)
        return validate_output(out, self.card, persona, list(refs), list(nums))

    def test_shape_and_intent(self):
        for malformed in (None, "{}", {}, []):
            self.assertTrue(validate_output(malformed, self.card, "expert", [], []))
        for fields in ({"intent": "answer"}, {"mentioned_entities": [3]}, {"self_check": {}}, {"extra": 1}):
            self.assertTrue(self.check("三号锅炉现在还好吗？", **fields))

    def test_chinese_ratio_and_length(self):
        self.assertIn("问题须以中文为主", self.check("Hello boiler OK?"))
        self.assertIn("问题须以中文为主", self.check("三号锅炉 temperature is too high, please check"))
        self.assertNotIn("问题须以中文为主", self.check("FAB-02线当前PLC状态及缓冲余量如何？"))
        for pid, n in [("novice", 41), ("reporter", 61), ("expert", 14), ("speculator", 71)]:
            self.assertTrue(any("字符" in e for e in self.check("锅" * n, pid)))

    def test_made_up_ids_and_partial_matches(self):
        for pid in PERSONA_IDS:
            for invented in ("BLR-039", "CLM-202611-001", "Line-X", "BLR-03-FAKE", "XYZ99"):
                errors = self.check(f"三号锅炉跟{invented}的记录好像不一样，麻烦你核对一下。", pid)
                self.assertIn("出现了场景卡以外的编号", errors)
        for pid in ("expert", "speculator"):
            self.assertTrue(self.check("麻烦调一下今天早班交接时的巡检记录看看。", pid))
        self.assertFalse(self.check("今天早班交接时，三号锅炉的排烟读数是多少？", "expert"))

    def test_answer_leak_and_question_number_exemption(self):
        row = {"user_question": "今天要吊装18吨的设备。", "ai_answer": "18 吨，库存4,200件，温度218℃。"}
        nums = _answer_numbers(row)
        for q in ("三号锅炉已经到 218 ℃ 了吗？", "库里是不是还有４２００件配件？"):
            self.assertIn("问题包含原回答的数值结论", self.check(q, nums=nums))
        self.assertFalse(self.check("那台行车今天要吊18吨的东西吗？", nums=nums))
        self.assertFalse(self.check("库里是不是还有14200件配件？", nums=nums))

    def test_similarity_reporter_and_novice_tools(self):
        original = "那台锅炉的声音听起来有点奇怪，帮我看看。"
        self.assertTrue(self.check(original[:-1] + "！", refs=["另一条原始问题", original]))
        self.assertTrue(self.check("我听见三号锅炉响了？你也听见了吗？", "reporter"))
        self.assertTrue(self.check("三号锅炉这个应该去看ops.alarm_history吗？"))
        self.assertFalse(self.check("我听见三号锅炉一直嗡嗡响，你看看。", "reporter"))

