"""重建第一版模板题库并按真实场景校验：python -m user_sim._fallback。"""
import json

from .catalog import DATA, REPO, _logs, load_scenarios
from .personas import PERSONA_IDS
from .validate import _answer_numbers, validate_output

# 每行依次为画像 novice、expert、speculator、reporter 的口吻。
# {name} 和 {id} 分别从该卡取中文实体名称和业务编号。
TEMPLATES = {
    "IND-001": ("diagnosis",
        "{name}那边冒出来的烟看着不对，是哪儿出毛病了？",
        "请对照今天早班的燃烧记录，{id}排烟温度波动的原因是什么？",
        "我怀疑是进风没调好，能翻一下{name}的燃烧记录核实吗？",
        "我刚从{name}旁边过，看见排烟温度那一栏一直在闪，你看看。"),
    "IND-002": ("decision",
        "{name}旁边的师傅走了，现在能按启动键了吗？",
        "{id}本班准备恢复供冷，维修签字和启动前检查都满足要求了吗？",
        "我怀疑{name}的保养单还差签字，帮我查查维修记录能否开机。",
        "{name}旁边还挂着检修牌，班长叫我过来等开机，你看看。"),
    "IND-011": ("status",
        "{name}嗡嗡响，现在还好吗？",
        "请核对今天白班的巡检记录，{id}运行时的声音还正常吗？",
        "我怀疑{name}的声音跟交班时不同，帮我核对巡检记录。",
        "巡到{name}跟前就听见一阵嗡嗡声，走远了又听不清了。"),
    "IND-016": ("progress",
        "{name}送来有一阵了，师傅那边弄到哪一步了？",
        "{id}今天交接前的参数核验进行到哪一步，试焊记录归档了吗？",
        "我怀疑{name}只装了参数还没试焊，帮我翻下调试记录。",
        "我看见{name}边上放着试焊的板子，交接本上那一格还空着。"),
    "IND-018": ("value",
        "{name}里面现在有多高，从哪儿看呀？",
        "请查{id}今天早班交接时的液位读数，并注明计量单位。",
        "我怀疑{name}显示的是上班的数，能查下监测记录里当前液位是多少吗？",
        "我在{name}旁边抄液位，屏上的数跳来跳去，看不清该记哪个。"),
    "IND-041": ("aggregate",
        "{name}这阵子漏过几回呀，能一起数数吗？",
        "请汇总{id}本月的密封泄漏记录，同一维修工单下的报修算一次。",
        "我怀疑{name}这月有重复报修，你能按维修记录核一下总次数吗？",
        "我看到交接本里好几页都写着{name}渗水，来回翻也数不清。"),
    "IND-045": ("compliance",
        "{name}上贴的小纸条卷起来了，还在能用的日子里吗？",
        "{id}本班用于出具尺寸报告，请核对计量证书是否仍在有效期内。",
        "我怀疑{name}贴的还是旧标签，帮我看看计量台账上的有效期。",
        "我看见{name}侧面贴了两张日期不同的校准标签，帮忙看看。"),
    "INS-A03": ("status",
        "客户把住院单子交了，他那份{name}现在还管用吗？",
        "请核实保单{id}在客户本次入院当天的状态，按当天的批单口径查。",
        "我怀疑{name}在入院前动过批单，能查下核心系统当日的保单状态吗？",
        "客户拿着{name}的单子来，说住院那天手机上看不到保单了。"),
    "INS-A04": ("progress",
        "客户一直等着，{name}那份申请现在办到哪儿了？",
        "请查{id}本次重疾申请的审核进度，病理材料已经签收了吗？",
        "我怀疑{name}那份病理材料还在收件环节，能翻一下受理记录吗？",
        "客户说{name}的病理报告交了好一会儿，手机上还没动静。"),
    "INS-A14": ("diagnosis",
        "飞机晚点了，客户的{name}怎么还没消息呀？",
        "客户反映航班延误后申请未有进展，请核对{id}的航班认定环节卡在哪里。",
        "我怀疑{name}登记的航班日期对不上，能查下航班记录核实原因吗？",
        "客户说航班都落地了，{name}那边还是查不到延误提示，帮忙看看。"),
    "INS-A15": ("decision",
        "狗狗做完手术，这个{name}能帮忙出点钱吗？",
        "请按手术当天生效的条款核对{id}，这次宠物手术是否属于可赔项目？",
        "我怀疑{name}对这类手术另有约定，帮我核下条款库能不能受理。",
        "客户把狗狗的手术单和{name}放在柜台上，说想报这笔费用。"),
    "INS-A18": ("value",
        "家里老人买了{name}，每个月能拿到手多少钱呀？",
        "请按本次申请的领取方式核算{id}，首期年金应发金额是多少？",
        "我怀疑{name}页面显示的是按年算的钱，帮我查条款核一下每月金额。",
        "客户指着{name}的领取单说想按月拿，没看懂每个月那一栏。"),
    "INS-A32": ("compliance",
        "客户那份{name}又续了一年，这张自费药单还合规矩吗？",
        "请核对{id}续保年度的用药条款，这张自费药清单符合报销条件吗？",
        "我怀疑{name}续保后换了用药目录，能对一下条款库里的适用条件吗？",
        "客户说{name}续上了，药房开的单上有自费标记，让我看看。"),
    "INS-A51": ("aggregate",
        "客户今年用过几回{name}，加起来还剩多少能报呀？",
        "请按本保单年度汇总{id}的既往给付，扣除已用部分后剩余额度多少？",
        "我怀疑{name}页面上少算了一次给付，帮我核对理赔台账里的累计金额。",
        "客户带来一叠{name}的报销单，说今年分开报了几回，想合起来看看。"),
}


def _build():
    cards = load_scenarios()
    answers = {row["case_id"]: _answer_numbers(row) for _, row in _logs(REPO)}
    rows = []
    for card in cards:
        case = card["scenario_id"]
        if case not in TEMPLATES:
            continue
        entities = card["entities"]
        named = next(e for e in entities if e["label"])
        numbered = next(e for e in entities if e["id"].isascii() and e["kind"] != "claim")
        intent, *templates = TEMPLATES[case]
        refs = [c["style_ref"] for c in cards if c["domain"] == card["domain"]]
        for persona, template in zip(PERSONA_IDS, templates):
            entity = numbered if "{id}" in template else named
            out = {"user_question": template.format(name=named["label"], id=numbered["id"]),
                   "intent": intent, "mentioned_entities": [entity["id"]],
                   "self_check": "按画像模板生成。"}
            errors = validate_output(out, card, persona, refs, answers[case])
            if errors:
                raise ValueError((case, persona, errors))
            rows.append({"scenario_id": case, "domain": card["domain"], "persona": persona,
                         "reviewed": False, **out})
    return rows


if __name__ == "__main__":
    (DATA / "fallback_questions.json").write_text(
        json.dumps(_build(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
