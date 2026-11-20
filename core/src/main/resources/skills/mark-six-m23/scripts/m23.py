# SPDX-License-Identifier: Apache-2.0
"""新澳门六合彩 · 23 码固定覆盖法（规则 M23-FROZEN-20261112）。

这是覆盖法,不是预测法:23 码固定不变,每期原样照买,命中概率恒为 23/49≈46.94%。
长期期望为负,请以娱乐支出看待。

用法:
  m23.py pick [--period 2026318] [--stake 10] [--payout 47] [--dir DIR]
  m23.py settle --period 2026318 --special 26 [--payout 47] [--dir DIR]
  m23.py stats [--last 100] [--payout 47] [--dir DIR]
  m23.py audit --codes 3,4,9
  m23.py bill [--period 2026318] [--stake 10] [--dir DIR]

默认数据目录 /workspace/qmx（不存在就在当前目录建 qmx）;
留痕:picks.jsonl 出号记录、settlements.jsonl 结算流水。
"""
import json
import os
import sys
from datetime import datetime

RULE = "M23-FROZEN-20261112"
FROZEN = [3, 4, 9, 10, 11, 12, 14, 15, 19, 20, 22, 23, 24,
          29, 30, 31, 32, 34, 36, 39, 42, 43, 46]
UNBOUGHT = [n for n in range(1, 50) if n not in FROZEN]
P_STR = {1: "马", 2: "蛇", 3: "龙", 4: "兔", 5: "虎", 6: "牛",
         7: "鼠", 8: "猪", 9: "狗", 10: "鸡", 11: "猴", 0: "羊"}


def zodiac(n):
    return P_STR[n % 12]


def default_dir():
    for base in ("/workspace", os.getcwd()):
        if os.path.isdir(base):
            return os.path.join(base, "qmx")
    return os.path.join(os.getcwd(), "qmx")


def store(d):
    os.makedirs(d, exist_ok=True)
    return d


def append(d, name, row):
    with open(os.path.join(d, name), "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load(d, name):
    p = os.path.join(d, name)
    if not os.path.exists(p):
        return []
    out = []
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def payout_net(payout, stake):
    """命中一码按 payout 倍(含本金)赔付,其余注全损。"""
    return stake * payout - stake * len(FROZEN)


def pick(period, stake, payout, d):
    row = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "period": period,
        "rule": RULE,
        "codes": FROZEN,
        "k": len(FROZEN),
        "stake_per_code": stake,
        "total_stake": stake * len(FROZEN),
        "coverage_pct": round(len(FROZEN) / 49 * 100, 2),
        "payout": payout,
        "hit_net": payout_net(payout, stake),
        "miss_net": -stake * len(FROZEN),
        "ev": round(len(FROZEN) / 49 * stake * payout - stake * len(FROZEN), 2),
        "zodiac_dist": {z: sum(1 for n in FROZEN if zodiac(n) == z) for z in
                        ["马", "蛇", "龙", "兔", "虎", "牛", "鼠", "猪", "狗", "鸡", "猴", "羊"]},
    }
    if period:
        append(store(d), "picks.jsonl", row)
    print(json.dumps({"ok": True, **row}, ensure_ascii=False))


def settle(period, special, payout, stake, d):
    hit = special in FROZEN
    log = [r for r in load(d, "settlements.jsonl") if r.get("period") != period]
    net = payout_net(payout, stake) if hit else -stake * len(FROZEN)
    log.append({
        "ts": datetime.now().isoformat(timespec="seconds"),
        "period": period, "special": special, "zodiac": zodiac(special),
        "hit": hit, "net": net, "rule": RULE, "payout": payout,
    })
    store(d)
    with open(os.path.join(d, "settlements.jsonl"), "w", encoding="utf-8") as f:
        for r in log:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    cum = sum(r["net"] for r in log)
    hits = sum(1 for r in log if r["hit"])
    print(json.dumps({
        "ok": True, "period": period, "special": special, "zodiac": zodiac(special),
        "hit": hit, "net": net, "cumulative_net": cum,
        "periods": len(log), "hits": hits,
        "hit_rate_pct": round(hits / len(log) * 100, 2) if log else 0,
        "theoretical_pct": round(len(FROZEN) / 49 * 100, 2),
    }, ensure_ascii=False))


def stats(last, payout, stake, d):
    rows = load(d, "settlements.jsonl")
    if last:
        rows = rows[-last:]
    n = len(rows)
    if not n:
        print(json.dumps({"ok": True, "periods": 0, "note": "还没有结算记录"}, ensure_ascii=False))
        return
    hits = sum(1 for r in rows if r["hit"])
    p = len(FROZEN) / 49
    z = (hits - n * p) / ((n * p * (1 - p)) ** 0.5) if n else 0
    print(json.dumps({
        "ok": True, "periods": n, "hits": hits,
        "hit_rate_pct": round(hits / n * 100, 2),
        "theoretical_pct": round(p * 100, 2),
        "z": round(z, 3),
        "significant": abs(z) >= 1.96,
        "net": sum(r["net"] for r in rows),
        "avg_net": round(sum(r["net"] for r in rows) / n, 2),
        "ev_per_period": round(p * stake * payout - stake * len(FROZEN), 2),
    }, ensure_ascii=False))


def bill(period, stake, d):
    codes = " ".join("%02d" % n for n in FROZEN)
    lines = [
        "# 新澳六合 · 23 码投注单",
        "",
        "- 期号：%s" % (period or "待定"),
        "- 规则：%s（冻结，号码不得变更）" % RULE,
        "- 玩法：新澳门六合彩 · 特码",
        "- 号码（%d 码）：%s" % (len(FROZEN), codes),
        "- 单码：¥%d　合计：¥%d" % (stake, stake * len(FROZEN)),
        "- 方式：平铺，不加仓、不补投、不换号",
        "",
        "未买（%d 码）：%s" % (len(UNBOUGHT), " ".join("%02d" % n for n in UNBOUGHT)),
        "",
        "> 固定覆盖法：命中率恒为 %.2f%%，长期期望为负，请以娱乐支出看待。"
        % (len(FROZEN) / 49 * 100),
    ]
    out = os.path.join(store(d), "bill_%s.md" % (period or "draft"))
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(json.dumps({"ok": True, "file": out, "period": period, "codes": FROZEN,
                      "total_stake": stake * len(FROZEN)}, ensure_ascii=False))


def audit(codes):
    s = set(codes)
    print(json.dumps({
        "ok": True,
        "same_as_frozen": s == set(FROZEN),
        "added": sorted(s - set(FROZEN)),
        "removed": sorted(set(FROZEN) - s),
        "warning": None if s == set(FROZEN) else "与冻结集合不一致：换码即构成新方法，须走变更协议",
    }, ensure_ascii=False))


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
    d = arg(argv, "--dir") or default_dir()
    stake = int(arg(argv, "--stake", 10))
    payout = int(arg(argv, "--payout", 47))
    if cmd == "pick":
        pick(arg(argv, "--period"), stake, payout, d)
    elif cmd == "settle":
        period = arg(argv, "--period")
        special = arg(argv, "--special")
        if not period or not special:
            raise SystemExit("settle 需要 --period 与 --special")
        settle(period, int(special), payout, stake, d)
    elif cmd == "stats":
        stats(int(arg(argv, "--last", 0) or 0), payout, stake, d)
    elif cmd == "bill":
        bill(arg(argv, "--period"), stake, d)
    elif cmd == "audit":
        codes = [int(x) for x in arg(argv, "--codes", "").replace(" ", "").split(",") if x]
        audit(codes)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv)