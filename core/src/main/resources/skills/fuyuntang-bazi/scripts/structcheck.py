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

# ─────────────────────── 宫位引动校验（--layer gongwei） ───────────────────────

GONG = {"年": "祖业/父母/童年", "月": "事业/兄弟/青年", "日": "婚姻/自身/中年", "时": "子女/晚年/下属"}
STRENGTH = {"冲": 5, "三合": 4, "半合": 4, "三会": 4, "六合": 4, "刑": 3, "害": 2, "破": 2, "伏吟": 1, "自刑": 3}


def _pillar_hits(zhi, pillars, layer_name):
    """某一层的支，引动了原局哪几柱。"""
    hits = []
    for p in pillars:
        rel = relation(zhi, p["支"])
        if rel:
            hits.append({"柱": p["柱"], "宫位领域": GONG[p["柱"]], "该柱地支": p["支"],
                         "引动方式": rel, "强度": STRENGTH.get(rel, 1),
                         "来源": "%s%s" % (layer_name, zhi)})
    # 三合/三会/三合局把相关柱一并算引动
    others = [(p["柱"], p["支"]) for p in pillars]
    for group, element in SANHE.items():
        if zhi not in group:
            continue
        mates = [(c, b) for c, b in others if b in group and b != zhi]
        uniq_branches = {b for _, b in mates}
        if len(uniq_branches) >= 2:
            rel = "三合" + element + "局"
            for c, b in mates:
                hits.append({"柱": c, "宫位领域": GONG[c], "该柱地支": b, "引动方式": rel,
                             "强度": STRENGTH["三合"], "来源": "%s%s" % (layer_name, zhi)})
        elif len(uniq_branches) == 1:
            rel = "半合" + element + "局"
            for c, b in mates:
                hits.append({"柱": c, "宫位领域": GONG[c], "该柱地支": b, "引动方式": rel,
                             "强度": STRENGTH["半合"], "来源": "%s%s" % (layer_name, zhi)})
    for group, element in SANHUI.items():
        if zhi not in group:
            continue
        mates = [(c, b) for c, b in others if b in group and b != zhi]
        if len({b for _, b in mates}) >= 2:
            rel = "三会" + element + "方"
            for c, b in mates:
                hits.append({"柱": c, "宫位领域": GONG[c], "该柱地支": b, "引动方式": rel,
                             "强度": STRENGTH["三会"], "来源": "%s%s" % (layer_name, zhi)})
    return hits


def gongwei(bazi_str, dayun=None, liunian=None):
    """宫位引动：这几柱里，哪几柱被大运/流年引动，以及怎么引动。"""
    pillars = parse_bazi(bazi_str)
    rows = []
    for p in pillars:
        row = {"柱": p["柱"], "地支": p["支"], "宫位领域": GONG[p["柱"]], "引动": []}
        for layer, gz in (("大运", dayun), ("流年", liunian)):
            if gz:
                rel = relation(gz[1], p["支"])
                if rel:
                    row["引动"].append({"来源": "%s%s" % (layer, gz[1]), "方式": rel,
                                       "强度": STRENGTH.get(rel, 1)})
        rows.append(row)
    # 三合/三会/半合这类跨柱引动单独列
    group_hits = []
    for layer, gz in (("大运", dayun), ("流年", liunian)):
        if not gz:
            continue
        for h in _pillar_hits(gz[1], pillars, layer):
            if "局" in h["引动方式"] or "方" in h["引动方式"]:
                group_hits.append(h)
    # 把合会引动并回对应柱，免得一张表里两处看
    for h in group_hits:
        for row in rows:
            if row["柱"] == h["柱"] and not any(x["来源"] == h["来源"] and x["方式"] == h["引动方式"] for x in row["引动"]):
                row["引动"].append({"来源": h["来源"], "方式": h["引动方式"], "强度": h["强度"]})
    for row in rows:
        row["引动"].sort(key=lambda x: -x["强度"])
    quiet = [r["柱"] for r in rows if not r["引动"]]
    return {
        "八字": " ".join(p["干"] + p["支"] for p in pillars),
        "宫位表": rows,
        "合会引动": group_hits,
        "无引动柱": quiet,
        "被引动柱": [r["柱"] for r in rows if r["引动"]],
        "断语要求": [
            "说某年有某事，必须指出落在哪一柱（年/月/日/时），以及引动方式（冲/合/刑/害/伏吟/半合）",
            "没有任何引动的柱，不许硬安事件",
            "同一事件跨两柱时，写清主次（日柱>月柱>时柱>年柱）",
        ],
    }


def audit_gongwei(text, bazi_str, dayun=None, liunian=None):
    """审断语里的宫位说法：声称被引动的柱与方式，必须在 gongwei 结果里成立。"""
    import re
    pillars = parse_bazi(bazi_str)
    g = gongwei(bazi_str, dayun, liunian)
    actual = {}
    for row in g["宫位表"]:
        actual[row["柱"]] = {x["方式"] for x in row["引动"]}
    for h in g["合会引动"]:
        actual.setdefault(h["柱"], set()).add(h["引动方式"])
    violations = []
    claims = re.findall(r"([年月日时])(柱|支)?(?:被|受|遭)?(冲|合|刑|害|伏吟|三合|半合|三会)", text)
    for pillar, _kind, rel in claims:
        got = actual.get(pillar, set())
        if not got:
            violations.append({"宫位": pillar, "声称": rel, "问题": "这一柱今年没有任何引动", "实际": "无"})
            continue
        # 合/半合/三合互认；三会单列
        ok = rel in got
        if not ok and rel in ("合", "半合", "三合"):
            ok = any("合" in x for x in got)
        if not ok:
            violations.append({"宫位": pillar, "声称": rel, "问题": "引动方式与实算不符", "实际": "、".join(sorted(got))})
    return {"被引动柱": g["被引动柱"], "违例": violations, "ok": not violations}
