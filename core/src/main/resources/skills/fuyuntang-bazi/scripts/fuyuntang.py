#!/usr/bin/env python3
"""福运堂八字 · ACS 技能入口。

子命令：
  paipan  --year 1990 --month 5 --day 12 --hour 14 --minute 30 --gender 男 [--calendar lunar] [--city 南宁 | --longitude 108.3]
  engine  --bazi "乙亥 乙酉 戊申 庚申" [--gender 男] [--age 30] [--modules core,marriage,career]
  rules   [--topic 排盘] [--max-chars 12000]
  predict add --bazi ... --item 婚姻 --expect ... --by 2027-01-01
  predict stats
  selftest
"""
import json
import os
import sys

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
    args = {"bazi": bazi, "gender": gender,
            "modules": (arg(argv, "--modules") or "core").split(",")}
    if arg(argv, "--age"):
        args["age"] = int(arg(argv, "--age"))
    print(fy_core.handle_mingli_engine(args))
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
    total = len(ANCHORS) + len(BOUNDARY)
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
