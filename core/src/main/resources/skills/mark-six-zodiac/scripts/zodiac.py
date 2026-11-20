# SPDX-License-Identifier: Apache-2.0
"""新澳六合 · 生肖分组与配额（规则 ZODIAC-FROZEN-20261120）。

生肖只用来分配覆盖面,不预测。单肖命中约 9%,低于恒押马 10.2%,已被证伪;
top3 覆盖约 29%(322期),随机基线 25%,未达显著。

用法:
  zodiac.py map
  zodiac.py quota --full 鸡 --empty 马
  zodiac.py audit --codes 3,4,9,10
  zodiac.py s4 --draws DRAW.json [--period 2026318]
  zodiac.py fill --codes 1,2,3 --top3 兔,虎,猪 --draws DRAW.json

draws.json 形如 [{"period":"2026317","regular":[31,49,30,22,43,24],"special":26}, ...]
（按 period 升序;没有该文件时 s4 会明确报错,不会瞎算。）
"""
import json
import os
import sys

ALL = ["马", "蛇", "龙", "兔", "虎", "牛", "鼠", "猪", "狗", "鸡", "猴", "羊"]
P_STR = {1: "马", 2: "蛇", 3: "龙", 4: "兔", 5: "虎", 6: "牛",
         7: "鼠", 8: "猪", 9: "狗", 10: "鸡", 11: "猴", 0: "羊"}
QUOTA = {"鸡": 4, "龙": 3, "鼠": 3, "羊": 3, "猴": 2, "猪": 2, "牛": 2,
         "蛇": 1, "虎": 1, "狗": 1, "兔": 1, "马": 0}
M23 = [3, 4, 9, 10, 11, 12, 14, 15, 19, 20, 22, 23, 24,
       29, 30, 31, 32, 34, 36, 39, 42, 43, 46]

# 文档《生肖购买方法完整说明》3.2 节的逐肖买法，用来核对配额生成器是否与冻结集合一致
FROZEN_BY_ZODIAC = {
    "鸡": [10, 22, 34, 46], "龙": [3, 15, 39], "鼠": [19, 31, 43], "羊": [12, 24, 36],
    "猴": [11, 23], "猪": [20, 32], "牛": [30, 42], "蛇": [14], "虎": [29],
    "狗": [9], "兔": [4], "马": [],
}
FROZEN_23 = sorted(n for v in FROZEN_BY_ZODIAC.values() for n in v)


def zodiac(n):
    return P_STR[n % 12]


def number_map():
    out = {z: [] for z in ALL}
    for n in range(1, 50):
        out[zodiac(n)].append(n)
    return out


def cmd_map():
    m = number_map()
    print(json.dumps({"ok": True, "zodiac": m,
                      "note": "生肖 = 号码 mod 12 查表；马 5 码，其余各 4 码（8=猪、10=鸡，勿写反）"},
                     ensure_ascii=False))


def cmd_quota(full, empty, frozen_mode=False):
    if frozen_mode:
        codes = FROZEN_23
        print(json.dumps({
            "ok": True, "mode": "frozen", "codes": codes, "k": len(codes),
            "coverage_pct": round(len(codes) / 49 * 100, 2),
            "by_zodiac": FROZEN_BY_ZODIAC,
            "note": "文档 3.2 节原样逐肖买法；与生成器(按口诀取每肖最小号)结果不同，核对时以本表为准",
        }, ensure_ascii=False))
        return
    if full not in ALL or empty not in ALL or full == empty:
        raise SystemExit("--full 与 --empty 必须是两个不同的生肖")
    m = number_map()
    order = [z for z in ALL if z not in (full, empty)]
    order.sort(key=lambda z: (-QUOTA.get(z, 0), z))
    codes = list(m[full])
    for z in order:
        codes.extend(m[z][:QUOTA.get(z, 0)])
    codes = sorted(codes)
    print(json.dumps({
        "ok": True, "codes": codes, "k": len(codes),
        "coverage_pct": round(len(codes) / 49 * 100, 2),
        "quota": {z: QUOTA.get(z, 0) for z in ALL},
        "full": full, "empty": empty,
        "note": "配额可复现；为什么是这个配额不可复现（推断为人工分配）",
    }, ensure_ascii=False))


def cmd_audit(codes):
    m = number_map()
    rows = {}
    for z in ALL:
        total = len(m[z])
        buy = [n for n in m[z] if n in codes]
        rows[z] = {"total": total, "buy": len(buy), "rate_pct": round(len(buy) / total * 100, 1),
                   "bought": buy, "lack": [n for n in m[z] if n not in codes]}
    print(json.dumps({"ok": True, "k": len(codes),
                      "coverage_pct": round(len(codes) / 49 * 100, 2),
                      "zodiac": rows}, ensure_ascii=False))



def issue_of(r):
    return str(r.get("issue") or r.get("period") or "")


def special_of(r):
    v = r.get("special")
    if v is None:
        raise SystemExit("开奖记录缺少 special（特码）：%s" % r)
    return int(v)


def load_draws(path):
    rows = json.load(open(path, encoding="utf-8"))
    rows.sort(key=lambda r: issue_of(r))
    return rows


def s4_scores(draws):
    """S4:压力分 = 0.6×minmax(遗漏期数) + 0.4×minmax(多窗口每码归一热榜)。"""
    n = len(draws)
    # 遗漏:该肖最近一次当特码距今多少期
    miss = {}
    for z in ALL:
        miss[z] = n
        for i in range(n - 1, -1, -1):
            if zodiac(special_of(draws[i])) == z:
                miss[z] = n - 1 - i
                break
    counts = {z: 0 for z in ALL}
    for z in ALL:
        for w in (30, 60, 120):
            seg = draws[-w:] if n >= w else draws
            c = 0
            for r in seg:
                for num in list(r.get("regular") or []) + [special_of(r)]:
                    if zodiac(num) == z:
                        c += 1
            counts[z] += (c / len(seg) if seg else 0) / len(number_map()[z]) / 3.0
    def minmax(d):
        lo, hi = min(d.values()), max(d.values())
        if hi - lo < 1e-12:
            return {k: 0.5 for k in d}
        return {k: (v - lo) / (hi - lo) for k, v in d.items()}
    a, b = minmax(miss), minmax(counts)
    score = {z: round(0.6 * a[z] + 0.4 * b[z], 4) for z in ALL}
    order = sorted(ALL, key=lambda z: -score[z])
    return score, order


def cmd_s4(draws_path, period):
    if not draws_path or not os.path.exists(draws_path):
        raise SystemExit("缺少 --draws：S4 必须有开奖历史，不能用估算代替")
    draws = load_draws(draws_path)
    if period:
        draws = [r for r in draws if issue_of(r) < str(period)]
    if len(draws) < 120:
        raise SystemExit("历史不足 120 期（当前 %d），S4 的三个窗口不齐，请先补数据" % len(draws))
    score, order = s4_scores(draws)
    print(json.dumps({"ok": True, "rule": "S4-frozen",
                      "top3": order[:3], "scores": score,
                      "based_on_periods": len(draws),
                      "based_until": issue_of(draws[-1])}, ensure_ascii=False))


def cmd_fill(codes, top3, draws_path):
    if not draws_path or not os.path.exists(draws_path):
        raise SystemExit("缺少 --draws：补码要按热榜挑号，必须有开奖历史")
    draws = load_draws(draws_path)
    m = number_map()
    codes = list(dict.fromkeys(codes))
    added, removed = [], []
    for z in top3:
        if any(n in codes for n in m[z]):
            continue
        # 该肖热榜最热的一码（并列取小号）
        best, bestc = None, -1
        for n in m[z]:
            c = sum(1 for r in draws[-120:] for x in list(r.get("regular") or []) + [special_of(r)] if x == n)
            if c > bestc:
                best, bestc = n, c
        if best is not None:
            added.append(best)
            codes.append(best)
    # 砍最冷的一码（只从非 top3 覆盖的生肖里挑，且不动新补的）
    if added:
        cands = [n for n in codes if n not in added and zodiac(n) not in top3]
        if cands:
            coldest = min(cands, key=lambda n: (sum(1 for r in draws[-120:] for x in list(r.get("regular") or []) + [r["special"]] if x == n), n))
            removed.append(coldest)
            codes.remove(coldest)
    print(json.dumps({"ok": True, "codes": sorted(codes), "k": len(codes),
                      "added": added, "removed": removed, "top3": top3},
                     ensure_ascii=False))


def cmd_verify():
    m = number_map()
    problems = []
    if len(m["马"]) != 5:
        problems.append("马的码数不是 5")
    for z in ALL:
        if z != "马" and len(m[z]) != 4:
            problems.append("%s 的码数不是 4" % z)
    if zodiac(8) != "猪":
        problems.append("8 应为猪，实为 %s" % zodiac(8))
    if zodiac(10) != "鸡":
        problems.append("10 应为鸡，实为 %s" % zodiac(10))
    if sum(len(v) for v in FROZEN_BY_ZODIAC.values()) != 23:
        problems.append("逐肖买法合计不是 23")
    m23 = [3, 4, 9, 10, 11, 12, 14, 15, 19, 20, 22, 23, 24, 29, 30, 31, 32, 34, 36, 39, 42, 43, 46]
    if FROZEN_23 != m23:
        problems.append("逐肖买法与 23 码冻结集合不一致：差 %s" %
                        sorted(set(FROZEN_23) ^ set(m23)))
    quota_sum = sum(QUOTA.values())
    if quota_sum != 23:
        problems.append("配额表合计不是 23(%d)" % quota_sum)
    print(json.dumps({
        "ok": not problems, "problems": problems,
        "checks": {
            "zodiac_8": zodiac(8), "zodiac_10": zodiac(10),
            "ma_codes": m["马"], "ma_count": len(m["马"]),
            "frozen_k": len(FROZEN_23), "matches_m23_frozen": FROZEN_23 == m23,
            "quota_sum": quota_sum,
        },
        "note": "verify 只检查结构不变量，不判断方法优劣",
    }, ensure_ascii=False, indent=0))


def arg(argv, name, default=None):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    cmd = argv[1]
    if cmd == "map":
        cmd_map()
    elif cmd == "quota":
        cmd_quota(arg(argv, "--full", "鸡"), arg(argv, "--empty", "马"), "--frozen" in argv)
    elif cmd == "verify":
        cmd_verify()
    elif cmd == "audit":
        codes = [int(x) for x in arg(argv, "--codes", "").replace(" ", "").split(",") if x]
        cmd_audit(codes)
    elif cmd == "s4":
        cmd_s4(arg(argv, "--draws"), arg(argv, "--period"))
    elif cmd == "fill":
        codes = [int(x) for x in arg(argv, "--codes", "").replace(" ", "").split(",") if x]
        top3 = [z for z in arg(argv, "--top3", "").split(",") if z]
        cmd_fill(codes, top3, arg(argv, "--draws"))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv)