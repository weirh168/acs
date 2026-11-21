#!/usr/bin/env python3
"""福运堂八字 · ACS 技能入口。

子命令：
  paipan  --year 1990 --month 5 --day 12 --hour 14 --minute 30 --gender 男 [--calendar lunar] [--city 南宁 | --longitude 108.3]
  engine  --bazi "乙亥 乙酉 戊申 庚申" [--gender 男] [--age 30] [--modules core,marriage,career]
  check   --bazi "乙丑 乙酉 乙丑 壬午" [--dayun 戊戌] [--liunian 丙午] [--text 已写好的断语] [--layer gongwei | --gongwei]
  rules   [--topic 排盘] [--max-chars 12000]
  predict add --bazi ... --item 婚姻 --expect ... --by 2027-01-01
  predict stats
  selftest
"""
import json
import os
import sys

# 不要在技能目录里生成 __pycache__：那会被一起打进 APK
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, "vendor"), HERE):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

def _install_lunar_python():
    """把 vendor/lunar_python 装成一个真正的包。

    安卓打包会丢掉 __init__.py，所以这里用 pkginit.py 的内容手工初始化三个包，
    之后 `from lunar_python import Solar, Lunar` 与官方用法完全一致。
    """
    import types
    vendor = os.path.join(HERE, "vendor")
    root = os.path.join(vendor, "lunar_python")
    if not os.path.isdir(root):
        return
    mapping = {"lunar_python": root,
               "lunar_python.util": os.path.join(root, "util"),
               "lunar_python.eightchar": os.path.join(root, "eightchar")}
    for name, path in mapping.items():
        if name in sys.modules:
            continue
        mod = types.ModuleType(name)
        mod.__path__ = [path]
        mod.__package__ = name
        import importlib.util as _ilu
        mod.__spec__ = _ilu.spec_from_loader(name, loader=None, is_package=True)
        sys.modules[name] = mod
    # 依赖顺序：util → eightchar → 根包（根包的 Lunar/EightChar 一导入就要用 util）
    order = ["lunar_python.util", "lunar_python.eightchar", "lunar_python"]
    for name in order:
        path = mapping[name]
        init = os.path.join(path, "pkginit.py")
        if not os.path.exists(init):
            continue
        with open(init, encoding="utf-8") as f:
            code = f.read()
        exec(compile(code, init, "exec"), sys.modules[name].__dict__)


_install_lunar_python()

import fy_core


def arg(argv, name, default=None):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    # 也认 --key=value，模型有时会拼成一整段
    prefix = name + "="
    for item in argv:
        if isinstance(item, str) and item.startswith(prefix):
            return item[len(prefix):]
    return default


def flag(argv, name):
    return name in argv


CITY_ALIAS = {"男": "male", "乾": "male", "乾造": "male", "male": "male",
              "女": "female", "坤": "female", "坤造": "female", "female": "female"}


def city_longitude(name):
    if not name:
        return None
    try:
        import json as _j
        with open(os.path.join(HERE, "cities.json"), encoding="utf-8") as f:
            table = _j.load(f)
    except Exception:
        return None
    if name in table:
        return table[name]
    for key, lon in table.items():
        if key in name or name in key:
            return lon
    return None


def cmd_paipan(argv):
    gender = CITY_ALIAS.get((arg(argv, "--gender") or "男").strip())
    if not gender:
        print(json.dumps({"ok": False, "error": "gender 只支持 男/女（或 male/female）"}, ensure_ascii=False))
        return 1
    lon = arg(argv, "--longitude")
    if lon is None:
        lon = city_longitude(arg(argv, "--city"))
    args = {
        "year": int(arg(argv, "--year")), "month": int(arg(argv, "--month")),
        "day": int(arg(argv, "--day")), "hour": int(arg(argv, "--hour")),
        "minute": int(arg(argv, "--minute") or 0),
        "calendar": arg(argv, "--calendar") or "solar",
        "gender": gender,
    }
    if lon is not None:
        args["longitude"] = float(lon)
    print(fy_core.handle_bazi_paipan(args))
    return 0


def cmd_engine(argv):
    bazi = arg(argv, "--bazi")
    if not bazi:
        print(json.dumps({"ok": False, "error": "缺少 --bazi，如 \"乙亥 乙酉 戊申 庚申\""}, ensure_ascii=False))
        return 1
    gender = CITY_ALIAS.get((arg(argv, "--gender") or "男").strip(), "male")
    mods = [m.strip() for m in (arg(argv, "--modules") or "core").split(",") if m.strip()]
    if "all" in mods:
        mods = ["core", "marriage", "career", "health", "education", "wealth", "yingqi"]
    args = {"bazi": bazi, "gender": gender, "modules": mods}
    if arg(argv, "--age"):
        args["age"] = int(arg(argv, "--age"))
    print(fy_core.handle_mingli_engine(args))
    return 0


def cmd_check(argv):
    import structcheck
    bazi = arg(argv, "--bazi")
    if not bazi:
        print(json.dumps({"ok": False, "error": "缺少 --bazi"}, ensure_ascii=False))
        return 1
    dayun = arg(argv, "--dayun")
    liunian = arg(argv, "--liunian") or arg(argv, "--year-gz")
    layer = "gongwei" if flag(argv, "--gongwei") else (arg(argv, "--layer") or "zhi").lower()
    try:
        if layer in ("gongwei", "gong", "宫位"):
            out = structcheck.gongwei(bazi, dayun, liunian)
            text_g = arg(argv, "--text")
            if text_g:
                out["宫位审核"] = structcheck.audit_gongwei(text_g, bazi, dayun, liunian)
                out["ok"] = out["宫位审核"]["ok"]
            else:
                out["ok"] = True
            print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
            return 0
        out = structcheck.check(bazi, dayun, liunian)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1
    text = arg(argv, "--text")
    if text:
        out["断语审核"] = structcheck.audit(text, bazi, dayun, liunian)
        out["ok"] = out["断语审核"]["ok"]
    else:
        out["ok"] = True
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    return 0


def cmd_rules(argv):
    args = {}
    if arg(argv, "--topic"):
        args["topic"] = arg(argv, "--topic")
    if arg(argv, "--max-chars"):
        args["max_chars"] = int(arg(argv, "--max-chars"))
    print(fy_core.handle_mingli_rules(args))
    return 0


def cmd_predict(argv):
    import predict_record as pr
    op = next((x for x in argv[1:] if not x.startswith("--") and x != "predict"), "stats")
    if op == "add":
        out = pr.add_prediction(bazi=arg(argv, "--bazi"), item=arg(argv, "--item"),
                                expect=arg(argv, "--expect"),
                                deadline=arg(argv, "--by") or arg(argv, "--deadline"))
    elif op == "verify":
        out = pr.verify_prediction(arg(argv, "--id"), (arg(argv, "--result") or ""))
    elif op == "overdue":
        out = pr.get_overdue()
    else:
        out = pr.get_stats()
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    return 0


# 基准值 = lunar_python 立春法实测（与原插件 .venv 同一份库、同一份 bazi.py）
ANCHORS = [((1900, 1, 1, 12, 0), "己亥 丙子 甲戌 庚午"),
           ((2000, 1, 1, 12, 0), "己卯 丙子 戊午 戊午"),
           ((1866, 11, 12, 8, 0), "丙寅 己亥 辛卯 壬辰"),
           ((2005, 10, 17, 21, 48), "乙酉 丙戌 甲戌 乙亥")]
# 立春法边界：2/4 仍属己卯年，2/5 才进庚辰年
BOUNDARY = [((2000, 2, 4, 12, 0), "己卯"), ((2000, 2, 5, 12, 0), "庚辰")]


def cmd_selftest(argv):
    ok = 0
    detail = []
    for (y, m, d, hh, mm), expect in ANCHORS:
        res = json.loads(fy_core.handle_bazi_paipan(
            {"year": y, "month": m, "day": d, "hour": hh, "minute": mm, "gender": "male"}))
        got = res.get("四柱")
        same = got == expect
        ok += 1 if same else 0
        detail.append({"公历": "%04d-%02d-%02d %02d:%02d" % (y, m, d, hh, mm),
                       "期望": expect, "实得": got, "一致": same,
                       "起运": res.get("起运"), "大运首步": (res.get("大运") or [{}])[0].get("干支")})
    eng = json.loads(fy_core.handle_mingli_engine({"bazi": "乙亥 乙酉 戊申 庚申", "gender": "male"}))
    rules = json.loads(fy_core.handle_mingli_rules({}))
    for (y, m, d, hh, mm), expect_year in BOUNDARY:
        res = json.loads(fy_core.handle_bazi_paipan(
            {"year": y, "month": m, "day": d, "hour": hh, "minute": mm, "gender": "male"}))
        got = (res.get("年柱") or "")
        same = got == expect_year
        ok += 1 if same else 0
        detail.append({"公历": "%04d-%02d-%02d 立春边界" % (y, m, d), "期望年柱": expect_year,
                       "实得年柱": got, "一致": same})
    # 结构校验回归：原局只有丑酉丑午，戌只能以「大运」出现；断语里出现辰/未必须被判违例
    try:
        import structcheck
        sc = structcheck.check("乙丑 乙酉 乙丑 壬午", "戊戌", "丙午")
        bad = structcheck.audit("大运戌冲辰、未戌相刑；原局酉丑半合金局", "乙丑 乙酉 乙丑 壬午", "戊戌", "丙午")
        good = structcheck.audit("大运戌与年支丑刑、与月支酉害；原局酉丑半合金局", "乙丑 乙酉 乙丑 壬午", "戊戌", "丙午")
        native_ok = set(sc["原局四支"].values()) == {"丑", "酉", "午"}
        dayun_ok = sc.get("大运", {}).get("支") == "戌" and any(x["关系"] == "刑" for x in sc["大运"]["与原局"])
        caught = bad["ok"] is False and {v["地支"] for v in bad["违例"]} == {"辰", "未"}
        passed = native_ok and dayun_ok and caught and good["ok"] is True
        ok += 1 if passed else 0
        detail.append({"检查": "结构校验回归（大运戌不得并入原局）", "原局锁定": native_ok,
                       "戌只在大运层": dayun_ok, "辰未被判串盘": caught, "正确断语通过": good["ok"], "一致": passed})
    except Exception as e:
        detail.append({"检查": "结构校验回归", "一致": False, "错误": str(e)})
    try:
        import structcheck as _sc
        g = _sc.gongwei("乙丑 乙酉 乙丑 壬午", "戊戌", "丙午")
        rows = {r["柱"]: {x["方式"] for x in r["引动"]} for r in g["宫位表"]}
        g_bad = _sc.audit_gongwei("月柱被冲，时柱被合。", "乙丑 乙酉 乙丑 壬午", "戊戌", "丙午")
        g_good = _sc.audit_gongwei("年支被刑、日支被刑，时支被合。", "乙丑 乙酉 乙丑 壬午", "戊戌", "丙午")
        layout_ok = ("刑" in rows.get("年", set()) and "刑" in rows.get("日", set())
                     and "害" in rows.get("月", set()) and any("合" in x for x in rows.get("时", set())))
        caught_g = g_bad["ok"] is False and any(v["宫位"] == "月" for v in g_bad["违例"])
        g_pass = layout_ok and caught_g and g_good["ok"] is True
        ok += 1 if g_pass else 0
        detail.append({"检查": "宫位引动回归（月酉只被害不冲）", "宫位表正确": layout_ok,
                       "错说法被判": caught_g, "对说法通过": g_good["ok"], "一致": g_pass})
    except Exception as e:
        detail.append({"检查": "宫位引动回归", "一致": False, "错误": str(e)})
    total = len(ANCHORS) + len(BOUNDARY) + 2
    out = {"ok": ok == total and eng.get("ok") is True and rules.get("ok") is True,
           "排盘锚点": detail, "引擎": "ok" if eng.get("ok") else eng.get("error"),
           "规则文件数": len(rules.get("规则文件") or [])}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out["ok"] else 1


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "paipan":
        return cmd_paipan(argv)
    if cmd == "engine":
        return cmd_engine(argv)
    if cmd == "check":
        return cmd_check(argv)
    if cmd == "rules":
        return cmd_rules(argv)
    if cmd == "predict":
        return cmd_predict(argv)
    if cmd == "selftest":
        return cmd_selftest(argv)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
