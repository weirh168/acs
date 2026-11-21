# -*- coding: utf-8 -*-
"""原盘结构校验：三层隔离 + 存在性校验。

三层各锁各的：
  原局   —— 四柱地支（年/月/日/时），只有这四个
  大运   —— 只有干支两个字，不得并入原局结构
  流年   —— 只有干支两个字，不得并入原局结构

任何刑冲合破害，先问「这两个支是不是都在同一层里」：
  在同一层 → 记为「层内结构」
  跨层     → 记为「大运×原局」或「流年×原局」，不许写成「原局…」

原文里出现的地支，必须能在三层集合里找到；找不到就是串盘，直接报违例。
"""

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"

CHONG = {"子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥"}
HE6 = {"子丑", "寅亥", "卯戌", "辰酉", "巳申", "午未"}
HAI = {"子未", "丑午", "寅巳", "卯辰", "申亥", "酉戌"}
PO = {"子酉", "卯午", "辰丑", "未戌", "寅亥", "巳申"}
XING_PAIRS = {"子卯", "丑戌", "未丑", "戌未", "寅巳", "巳申", "寅申"}
XING_SELF = set("辰午酉亥")
SANHE = {"申子辰": "水", "亥卯未": "木", "寅午戌": "火", "巳酉丑": "金"}
SANHUI = {"寅卯辰": "木", "巳午未": "火", "申酉戌": "金", "亥子丑": "水"}


def _pair(a, b):
    return a + b if ZHI.index(a) <= ZHI.index(b) else b + a


def relation(a, b):
    """两个地支之间成立的关系（不含三合/三会这种需要第三支的）。"""
    if a == b:
        return "自刑" if a in XING_SELF else "伏吟"
    p = _pair(a, b)
    for name, table in (("冲", CHONG), ("六合", HE6), ("害", HAI), ("破", PO), ("刑", XING_PAIRS)):
        if p in table:
            return name
    return None


def sanhe_groups(branches):
    """返回已成的三合/半合，以及三会。"""
    out = []
    uniq = list(dict.fromkeys(branches))
    for group, element in SANHE.items():
        hit = [b for b in uniq if b in group]
        if len(hit) == 3:
            out.append({"关系": "三合" + element + "局", "涉及": "".join(hit)})
        elif len(hit) == 2:
            out.append({"关系": "半合" + element + "局", "涉及": "".join(hit)})
    for group, element in SANHUI.items():
        hit = [b for b in uniq if b in group]
        if len(hit) == 3:
            out.append({"关系": "三会" + element + "方", "涉及": "".join(hit)})
    return out


def parse_bazi(bazi_str):
    parts = [p for p in bazi_str.replace(",", " ").split() if p]
    if len(parts) != 4 or any(len(p) != 2 for p in parts):
        raise ValueError("八字要四个两字柱，如 '乙丑 乙酉 乙丑 壬午'")
    labels = ["年", "月", "日", "时"]
    return [{"柱": labels[i], "干": parts[i][0], "支": parts[i][1]} for i in range(4)]


def _layer_relations(pillars, with_position=True):
    out = []
    n = len(pillars)
    for i in range(n):
        for j in range(i + 1, n):
            rel = relation(pillars[i]["支"], pillars[j]["支"])
            if not rel:
                continue
            out.append({
                "关系": rel,
                "涉及": pillars[i]["支"] + pillars[j]["支"],
                "位置": "%s%s-%s%s" % (pillars[i]["柱"], pillars[i]["支"], pillars[j]["柱"], pillars[j]["支"])
                if with_position else "",
            })
    for g in sanhe_groups([p["支"] for p in pillars]):
        out.append({"关系": g["关系"], "涉及": g["涉及"], "位置": "原局"})
    return out


def _cross(target_zhi, pillars, layer_name):
    out = []
    for p in pillars:
        rel = relation(target_zhi, p["支"])
        if rel:
            out.append({
                "关系": rel,
                "涉及": target_zhi + p["支"],
                "对位": "%s支%s" % (p["柱"], p["支"]),
                "写法": "%s%s与%s支%s%s" % (layer_name, target_zhi, p["柱"], p["支"], rel),
            })
    others = [p["支"] for p in pillars]
    for group, element in SANHE.items():
        if target_zhi in group:
            mate = [b for b in others if b in group and b != target_zhi]
            if len(set(mate)) >= 2:
                out.append({"关系": "三合" + element + "局", "涉及": target_zhi + "".join(dict.fromkeys(mate)),
                            "对位": "原局", "写法": "%s%s与原局%s三合%s局" % (layer_name, target_zhi, "".join(dict.fromkeys(mate)), element)})
            elif mate:
                out.append({"关系": "半合" + element + "局", "涉及": target_zhi + mate[0],
                            "对位": "原局", "写法": "%s%s与%s支%s半合%s局" % (layer_name, target_zhi, "原局" + mate[0], mate[0], element)})
    for group, element in SANHUI.items():
        if target_zhi in group:
            mate = [b for b in others if b in group and b != target_zhi]
            if len(set(mate)) >= 2:
                out.append({"关系": "三会" + element + "方", "涉及": target_zhi + "".join(dict.fromkeys(mate)),
                            "对位": "原局", "写法": "%s%s与原局%s三会%s方" % (layer_name, target_zhi, "".join(dict.fromkeys(mate)), element)})
    return out


def check(bazi_str, dayun=None, liunian=None):
    """三层隔离的结构清单。dayun/liunian 传干支两字，如 '戊戌'、'丙午'。"""
    pillars = parse_bazi(bazi_str)
    native = [p["支"] for p in pillars]
    result = {
        "八字": " ".join(p["干"] + p["支"] for p in pillars),
        "原局四支": {p["柱"]: p["支"] for p in pillars},
        "锁定集合": {"原局": native},
        "层内结构": _layer_relations(pillars),
        "禁止项": [
            "大运地支不得写进原局结构（不能说「原局戌冲辰」，辰若不在原局，这句话从根上错）",
            "流年地支同样不得并入原局；跨层关系必须标「大运×原局」「流年×原局」",
            "原局四支以外的地支，除非是运/年本身，否则不得出现在断语里",
        ],
    }
    used = set(native)
    if dayun:
        if len(dayun) != 2:
            raise ValueError("大运要两字，如 '戊戌'")
        result["大运"] = {"干支": dayun, "支": dayun[1], "与原局": _cross(dayun[1], pillars, "大运")}
        used.add(dayun[1])
        result["锁定集合"]["大运"] = dayun[1]
    if liunian:
        if len(liunian) != 2:
            raise ValueError("流年要两字，如 '丙午'")
        result["流年"] = {"干支": liunian, "支": liunian[1], "与原局": _cross(liunian[1], pillars, "流年")}
        used.add(liunian[1])
        result["锁定集合"]["流年"] = liunian[1]
    if dayun and liunian:
        rel = relation(dayun[1], liunian[1])
        result["运年之间"] = ({"关系": rel, "涉及": dayun[1] + liunian[1],
                            "写法": "大运%s与流年%s%s" % (dayun[1], liunian[1], rel)} if rel else [])
    result["锁定集合"]["全部合法地支"] = "".join(sorted(used, key=ZHI.index))
    return result


def audit(text, bazi_str, dayun=None, liunian=None):
    """审一段断语：出现的地支必须属于原局/大运/流年三层之一，否则算串盘。"""
    pillars = parse_bazi(bazi_str)
    layers = {"原局": {p["支"] for p in pillars}}
    if dayun:
        layers["大运"] = {dayun[1]}
    if liunian:
        layers["流年"] = {liunian[1]}
    legal = set().union(*layers.values())
    found = {}
    for ch in text:
        if ch in ZHI:
            found[ch] = found.get(ch, 0) + 1
    violations = []
    for zhi in sorted(found, key=ZHI.index):
        if zhi not in legal:
            violations.append({
                "地支": zhi,
                "问题": "不属于原局、大运、流年任何一层",
                "后果": "这类句子（如「%s冲%s」）是把别的盘的地支搬进来了" % (zhi, next(iter(legal))),
            })
    counts = {name: sum(1 for ch in text if ch in zhis) for name, zhis in layers.items()}
    return {
        "合法地支": "".join(sorted(legal, key=ZHI.index)),
        "出现的地支": "".join(sorted(found, key=ZHI.index)),
        "各层出现次数": counts,
        "违例": violations,
        "ok": not violations,
    }
