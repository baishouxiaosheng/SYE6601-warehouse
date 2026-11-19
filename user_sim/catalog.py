"""场景卡构建（SPEC §3）。用法：python -m user_sim.catalog --out user_sim/data/scenarios.json [--loopb-root PATH]"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
INDUSTRIAL_LOG_GLOB = "111/工业智能体模拟监控日志_60条*.json"
INSURANCE_LOG_GLOB = "111/保险智能体日志集_INS-A03至A62_合并.json"
POLICY_PATH = REPO / "confidence_07a" / "policy" / "scorecard_policy.v2.json"


DATA = Path(__file__).with_name("data")
TOPICS = {
    "吊装放行": ("吊装", "lift_plan"), "排放数据": ("排放", "废水"),
    "排烟温度": ("排烟",), "库存余量": ("库存", "库房", "备件"),
    "作业许可": ("作业证", "许可证", "动火", "有限空间", "受限空间"),
    "配方核对": ("配方", "固化温度", "添加剂"), "供料状态": ("供料", "缓冲"),
    "热处理报告": ("热处理报告",), "焊机调试": ("焊机",), "储罐液位": ("液位",),
    "压力监测": ("压力读数", "操作压力"), "设备冷却": ("冷却系统",),
    "采购进度": ("采购", "供应商"), "电能质量": ("电能质量",), "温度监测": ("反应釜现在温度",),
    "大修进度": ("大修",), "工单积压": ("待处理的工单",), "阀门操作": ("排料阀",),
    "空气质量": ("空气质量",), "噪声合规": ("噪声",), "故障诊断": ("错误代码",),
    "产线产量": ("产量",), "质量检验": ("质检", "良率", "抛料", "合格", "检完", "送检"),
    "设备校准": ("标定", "校准", "读数准"), "开机检查": ("开机", "启动", "恢复生产"),
    "设备诊断": ("怎么回事", "原因", "异响", "故障", "报警", "跳车", "泄漏", "振动"),
    "能源消耗": ("电费", "能耗", "节能"), "设备保养": ("保养", "维护", "维修"),
    "理赔限额": ("累计限额", "免赔", "限额"), "续保状态": ("续保",),
    "定损进度": ("定损",), "年金领取": ("年金",), "保单贷款": ("保单贷款",),
    "理赔金额": ("能报多少", "能赔多少", "能领多少", "摊回多少"),
    "理赔责任": ("能赔", "能不能赔", "保障", "claims.", "policy_database."),
}
INTENT_WORDS = {
    "status": ("状态", "正常", "怎么样", "情况", "了吗", "怎样"),
    "value": ("多少", "几", "数值", "读数"),
    "decision": ("能不能", "可以", "可否", "放行", "开机", "赔吗", "能赔", "能进", "能报"),
    "diagnosis": ("为什么", "原因", "怎么回事", "是不是因为", "异响", "怎么处理"),
    "compliance": ("合规", "超标", "有效期", "证书", "资质", "过期", "合格"),
    "aggregate": ("合计", "总共", "累计", "够不够", "还够", "够明天"),
    "progress": ("进度", "出来了吗", "到哪一步", "拿到了", "到货", "完成", "办下来"),
}
KINDS = {
    "asset": {"asset_id", "asset_tag", "equipment_id"},
    "line": {"line_id", "line", "from_line", "to_line"},
    "batch": {"batch_id", "batch_ids", "batch_number", "lot", "lot_id"},
    "material": {"material", "material_id", "material_code", "sku", "skus", "part", "part_id"},
    "claim": {"claim_id"}, "policy": {"policy_id", "reinsurance_policy_id"},
}
CHINESE = re.compile(r"[\u3400-\u9fff]")
SYNTHETIC = re.compile(r"SIM\d{2}-", re.I)


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _logs(repo_root):
    for domain, pattern in (("industrial", INDUSTRIAL_LOG_GLOB), ("insurance", INSURANCE_LOG_GLOB)):
        path, = sorted(repo_root.glob(pattern))
        for row in _read(path):
            yield domain, row


def _add_entities(entities, args, result):
    for key, value in args.items():
        if key in {"query", "collection", "from", "to", "as_of", "window", "period",
                   "insured_id_number", "voltage", "date", "time"} or key.startswith(("date_", "lookback_")):
            continue
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, dict):
                _add_entities(entities, item, result)
                continue
            if not isinstance(item, str) or SYNTHETIC.search(item):
                continue
            kind = next((k for k, keys in KINDS.items() if key in keys), "other")
            if key in {"display_name", "name", "equipment_name"} and CHINESE.search(item):
                kind, label = "asset", item
            else:
                if not re.fullmatch(r"[A-Za-z0-9]+(?:[-_.][A-Za-z0-9]+)*", item):
                    continue
                if not re.search("[A-Za-z]", item) or not (re.search(r"\d", item) or
                        re.fullmatch(r"Line-[A-Za-z]+", item, re.I) or (kind == "line" and "-" in item)):
                    continue
                if re.match(r"\d{4}-\d\d-\d\d|^\d+(?:min|h|days?|kg|kV)$", item, re.I):
                    continue
                labels = ["description", "name", "model"]
                if kind == "policy":
                    labels.append("product_name")
                label = next((result[k] for k in labels if isinstance(result.get(k), str) and result[k]), "")
            existing = next((e for e in entities if e["id"] == item), None)
            if existing is not None:
                if not existing["label"]:
                    existing["label"] = label
            elif len(entities) < 8:
                entities.append({"id": item, "kind": kind, "label": label})


def _loopb_records(node):
    if isinstance(node, list):
        for child in node:
            yield from _loopb_records(child)
    elif isinstance(node, dict):
        if "family" in node:
            if node["family"] == "SOURCE":
                yield node
        else:
            for child in node.values():
                yield from _loopb_records(child)


def _supplement(cards, root, runs, contexts):
    for domain in ("industrial", "insurance"):
        group = [card for card in cards if card["domain"] == domain]
        for path in sorted((root / "databases" / domain).glob("*.json")):
            for rec in _loopb_records(_read(path)):
                provenance = rec.get("provenance", {})
                ctx = provenance.get("observed_task_context", {})
                lookup = rec.get("lookup", {})
                if isinstance(ctx, str):
                    ctx = {"case_id": ctx}
                if not isinstance(ctx, dict) or not isinstance(lookup, dict):
                    continue
                if SYNTHETIC.search(json.dumps(provenance, ensure_ascii=False)):
                    continue
                case = (ctx.get("case_id") or provenance.get("case_id") or
                        provenance.get("source_case_id") or rec.get("case_id"))
                run = ctx.get("run_id") or provenance.get("run_id") or provenance.get("source_run_id")
                visible = ctx.get("visible_context", ctx)
                if not isinstance(visible, dict):
                    continue
                if case or run:
                    case = case or runs.get(run)
                    matches = [card for card in group if card["scenario_id"] == case]
                else:
                    keys = {"site", "workshop", "claim_id", "policy_id", "received_at"} & visible.keys()
                    matches = [card for card in group if keys and all(
                        contexts[card["scenario_id"]].get(k) == visible[k] for k in keys)]
                if len(matches) == 1:
                    entities = matches[0]["entities"]
                    _add_entities(entities, lookup, {})
                    _add_entities(entities, {k: v for k, v in visible.items()
                                             if k not in {"run_id", "case_id"}}, {})


def build_scenarios(repo_root: Path = REPO, loopb_root: Optional[Path] = None) -> List[Dict]:
    """返回全部场景卡（工业 + 保险），字段与 SPEC §3 一致。"""
    risk_words = _read(repo_root / POLICY_PATH.relative_to(REPO))["high_risk"]["lexicon"]
    cards, runs, contexts = [], {}, {}
    for domain, row in _logs(repo_root):
        question = row["user_question"]
        tools, entities = [], []
        for event in row["trace"]:
            if event["event"] == "tool_call":
                tools.append(event["tool"])
                result = event.get("result")
                _add_entities(entities, event["arguments"], result if isinstance(result, dict) else {})
        tools = list(dict.fromkeys(tools))
        subject = " ".join([question, *tools])
        default = "现场运行" if domain == "industrial" else "理赔责任"
        topic = next((topic for topic, words in TOPICS.items() if any(w in subject for w in words)), default)
        cards.append({
            "scenario_id": row["case_id"], "domain": domain,
            "context": {k: v for k, v in row["visible_context"].items() if k != "received_at"},
            "entities": entities, "topic": topic,
            "intent_hints": [i for i, words in INTENT_WORDS.items() if any(w in question for w in words)],
            "tools": tools, "risk": "high" if any(w in subject for w in risk_words) else "normal",
            "style_ref": question,
            "data_date": str(row["visible_context"].get("received_at", ""))[:10],
        })
        runs[row["run_id"]] = row["case_id"]
        contexts[row["case_id"]] = row["visible_context"]
    if loopb_root is not None:
        _supplement(cards, loopb_root, runs, contexts)
    return cards


def load_scenarios(path: Optional[Path] = None) -> List[Dict]:
    """读取已提交的 user_sim/data/scenarios.json；不存在时现场构建。"""
    source = path or DATA / "scenarios.json"
    return _read(source) if source.exists() else build_scenarios()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="从仓库日志构建场景卡")
    parser.add_argument("--out", type=Path, default=DATA / "scenarios.json")
    parser.add_argument("--loopb-root", type=Path)
    args = parser.parse_args(argv)
    cards = build_scenarios(loopb_root=args.loopb_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(cards, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
