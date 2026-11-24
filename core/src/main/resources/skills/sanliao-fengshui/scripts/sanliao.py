#!/usr/bin/env python3
"""三僚风水用的定式计算:二十四山、双山五行、三合局。

只做各家一致的定式(罗盘分工、双山五行、三合六合三会),不做各家有分歧的断法。
用法:
  python3 sanliao.py shan --degree 187.5
  python3 sanliao.py list
  python3 sanliao.py sanhe --shan 子
"""
import argparse
import json
import sys

MOUNTAINS = ["子", "癸", "丑", "艮", "寅", "甲", "卯", "乙", "辰", "巽", "巳", "丙",
             "午", "丁", "未", "坤", "申", "庚", "酉", "辛", "戌", "乾", "亥", "壬"]

# 双山:每两山一宫,从壬子起,顺时针
PAIRS = ["壬子", "癸丑", "艮寅", "甲卯", "乙辰", "巽巳", "丙午", "丁未", "坤申", "庚酉", "辛戌", "乾亥"]
PAIR_ELEMENT = ["水", "金", "火", "木", "水", "金", "火", "木", "水", "金", "火", "木"]

# 后天八卦方位(与二十四山对齐:每卦三山)
BAGUA = {
    "坎": ["壬", "子", "癸"], "艮": ["丑", "艮", "寅"], "震": ["甲", "卯", "乙"], "巽": ["辰", "巽", "巳"],
    "离": ["丙", "午", "丁"], "坤": ["未", "坤", "申"], "兑": ["庚", "酉", "辛"], "乾": ["戌", "乾", "亥"],
}

SANHE = {"水": "申子辰", "金": "巳酉丑", "火": "寅午戌", "木": "亥卯未"}
# 三会按山本身的地支定,与双山五行无关
ZHIS = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
SANHUI_BY_ZHI = {}
for _start, _ju, _el in ((2, "寅卯辰", "木"), (5, "巳午未", "火"), (8, "申酉戌", "金"), (11, "亥子丑", "水")):
    for _k in range(3):
        SANHUI_BY_ZHI[ZHIS[(_start + _k) % 12]] = _ju
XING = {"水": "申", "金": "巳", "火": "寅", "木": "亥"}
LIUHE = {"子": "丑", "丑": "子", "寅": "亥", "亥": "寅", "卯": "戌", "戌": "卯",
         "辰": "酉", "酉": "辰", "巳": "申", "申": "巳", "午": "未", "未": "午"}


def mountain_of(degree: float) -> tuple[int, float]:
    """返回(山序号, 距子山正中的角度)。正北 0°,顺时针。"""
    d = degree % 360.0
    # 子山中心是 0°,每山 15°
    idx = int((d + 7.5) // 15) % 24
    return idx, d


def sanhui_of(mountain: str, pair: str) -> str:
    """三会:山本身是地支就用它,天干/四维借用双山里那个地支。"""
    if mountain in SANHUI_BY_ZHI:
        return SANHUI_BY_ZHI[mountain]
    for ch in pair:
        if ch in SANHUI_BY_ZHI:
            return SANHUI_BY_ZHI[ch]
    return ""


def describe(degree: float) -> dict:
    idx, d = mountain_of(degree)
    mountain = MOUNTAINS[idx]
    pair_idx = ((idx + 1) // 2) % 12
    pair = PAIRS[pair_idx]
    element = PAIR_ELEMENT[pair_idx]
    gua = next((g for g, ms in BAGUA.items() if mountain in ms), "")
    # 兼向:落在这山靠边的三分之一,习惯上算兼
    offset = (degree % 360.0) - (idx * 15.0)
    while offset > 7.5:
        offset -= 15.0
    jian = abs(offset) > 5.0
    return {
        "degree": round(degree % 360.0, 2),
        "shan": mountain,
        "offset_in_shan": round(offset, 2),
        "off_center_gt5": jian,
        "shuangkou": pair + ("山" if False else ""),
        "shuangkou_element": element,
        "sanhe_ju": SANHE.get(element, ""),
        "sanhui_ju": sanhui_of(shan, PAIRS[pair_idx]),
        "xing": XING.get(element, ""),
        "liuhe": LIUHE.get(mountain, ""),
        "bagua": gua,
        "mountain_span": f"{(idx * 15 - 7.5) % 360:.1f}°–{(idx * 15 + 7.5) % 360:.1f}°",
    }


def cmd_shan(args) -> dict:
    return describe(float(args.degree))


def cmd_list(_args) -> dict:
    rows = []
    for i, m in enumerate(MOUNTAINS):
        pair_idx = ((i + 1) // 2) % 12
        rows.append({
            "shan": m,
            "center": round(i * 15.0, 1),
            "shuangkou": PAIRS[pair_idx],
            "element": PAIR_ELEMENT[pair_idx],
            "bagua": next((g for g, ms in BAGUA.items() if m in ms), ""),
        })
    return {"mountains": rows, "note": "度数按正北 0°、顺时针;每山 15°"}


def cmd_sanhe(args) -> dict:
    shan = args.shan.strip()
    if shan not in MOUNTAINS:
        return {"error": f"不认识的二十四山名:{shan}"}
    idx = MOUNTAINS.index(shan)
    pair_idx = ((idx + 1) // 2) % 12
    element = PAIR_ELEMENT[pair_idx]
    return {
        "shan": shan,
        "shuangkou": PAIRS[pair_idx],
        "element": element,
        "sanhe_ju": SANHE.get(element, ""),
        "sanhui_ju": sanhui_of(shan, PAIRS[pair_idx]),
        "xing": XING.get(element, ""),
        "liuhe": LIUHE.get(shan, ""),
        "bagua": next((g for g, ms in BAGUA.items() if shan in ms), ""),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("shan")
    s.add_argument("--degree", required=True)
    sub.add_parser("list")
    h = sub.add_parser("sanhe")
    h.add_argument("--shan", required=True)
    args = ap.parse_args()
    data = {"shan": cmd_shan, "list": cmd_list, "sanhe": cmd_sanhe}[args.cmd](args)
    print(json.dumps(data, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
