# SPDX-License-Identifier: Apache-2.0
"""新澳六合 · 热榜数据驱动出码（M23-DATA-v1）。

与 23 码冻结法(M23-FROZEN)并行:冻结法是固定覆盖,本脚本按开奖历史里的热榜出码。
两者命中概率都是「买入码数/49」,期望都为负;区别只在选号依据,不是预测模型。

用法:
  m23data.py record --issue 2026323 --regular 33,8,29,15,41,23 --special 47 [--dir DIR]
  m23data.py analyze [--dir DIR] [--window 120]
  m23data.py combo [--dir DIR] [--k 23] [--window 120] [--max-age-hours 72]
  m23data.py status [--dir DIR]
  m23data.py set-pick --issue 2026323 [--dir DIR]

数据文件 draws.json（与 zodiac 技能共用）:
  [{"issue":"2026323","regular":[33,8,29,15,41,23],"special":47,"recorded":"2026-11-20T21:40:00"}, ...]
"""
import json
import os
import sys
from datetime import datetime

W30, W60, W120 = 30, 60, 120


def base_dir():
    for b in ("/workspace", os.getcwd()):
        if os.path.isdir(b):
            return os.path.join(b, "qmx")
    return "qmx"


def paths(d):
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "draws.json"), os.path.join(d, "picks.jsonl")


def load(d):
    p, _ = paths(d)
    if not os.path.exists(p):
        return []
    rows = json.load(open(p, encoding="utf-8"))
    rows.sort(key=lambda r: str(r["issue"]))
    return rows


def save(d, rows):
    p, _ = paths(d)
    json.dump(rows, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)


def arg(argv, name, default=None):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def nums(s):
    return [int(x) for x in str(s).replace(" ", "").split(",") if x]



def freshness(rows, max_age_hours):
    """最新一期是不是新抓的:看 recorded 时间。过期就拒绝出码(铁律:必须用当时热榜)。"""
    from datetime import datetime as _dt
    if not rows:
        return False, None, "没有任何历史数据"
    rec = rows[-1].get("recorded")
    if not rec:
        return False, None, "最新一期没有记录抓取时间，无法确认是否为当时数据；请重新 record"
    try:
        when = _dt.fromisoformat(rec)
    except ValueError:
        return False, None, "抓取时间格式不对：%s" % rec
    age = (_dt.now() - when).total_seconds() / 3600.0
    ok = age <= max_age_hours
    msg = ("最新一期 %s 抓于 %.1f 小时前，可用" % (rows[-1]["issue"], age)) if ok else \
          ("最新一期 %s 抓于 %.1f 小时前，超过 %.0f 小时，数据不是当期的；必须重新抓取后再出码" %
           (rows[-1]["issue"], age, max_age_hours))
    return ok, round(age, 1), msg


def cmd_record(d, issue, regular, special):
    if not issue:
        raise SystemExit("record 需要 --issue")
    if len(regular) != 6 or len(set(regular)) != 6:
        raise SystemExit("正码必须 6 个且不重复，收到 %d 个: %s" % (len(regular), regular))
    if special in regular:
        raise SystemExit("特码不能与正码重复")
    for n in regular + [special]:
        if not 1 <= n <= 49:
            raise SystemExit("号码超出 1-49: %d" % n)
    rows = [r for r in load(d) if str(r["issue"]) != str(issue)]
    rows.append({"issue": str(issue), "regular": regular, "special": special,
                 "recorded": datetime.now().isoformat(timespec="seconds")})
    save(d, rows)
    print(json.dumps({"ok": True, "issue": issue, "regular": regular, "special": special,
                      "total_draws": len(rows)}, ensure_ascii=False))


def score(rows, window):
    """热榜分：近 30 期权重 1.0、31-60 期 0.5、61-120 期 0.25；全部号码(正码+特码)口径。"""
    seg = rows[-window:] if window else rows
    n = len(seg)
    freq = {x: 0.0 for x in range(1, 50)}
    for i, r in enumerate(seg):
        back = n - 1 - i
        w = 1.0 if back < W30 else (0.5 if back < W60 else 0.25)
        for x in list(r.get("regular") or []) + [r["special"]]:
            freq[x] += w
    last = {}
    for i, r in enumerate(rows):
        for x in list(r.get("regular") or []) + [r["special"]]:
            last[x] = i
    miss = {x: (len(rows) - 1 - last[x]) if x in last else len(rows) for x in range(1, 50)}
    return seg, freq, miss


def hot_tail(freq, top):
    tot = {}
    for x, f in freq.items():
        tot[x % 10] = tot.get(x % 10, 0.0) + f
    order = sorted(tot.items(), key=lambda kv: -kv[1])
    return [t for t, _ in order[:top]]


def cmd_analyze(d, window):
    rows = load(d)
    if len(rows) < 30:
        raise SystemExit("历史不足 30 期（当前 %d 期），先 record 补数据再分析" % len(rows))
    seg, freq, miss = score(rows, window)
    hot = sorted(range(1, 50), key=lambda x: (-freq[x], -miss[x]))
    cold = sorted(range(1, 50), key=lambda x: (freq[x], -miss[x]))
    sp = (seg[-1] or {}).get("special")
    print(json.dumps({
        "ok": True, "draws": len(rows), "latest_issue": str(seg[-1]["issue"]),
        "latest_special": sp,
        "hot_top10": hot[:10], "hot_scores": {str(x): round(freq[x], 2) for x in hot[:10]},
        "cold_top10": cold[:10],
        "never_seen": [x for x in range(1, 50) if miss[x] >= len(rows)],
        "hot_tail_3": hot_tail(freq, 3), "cold_tail_3": [t for t, _ in sorted(
            {x % 10: 0 for x in range(1, 50)}.items())[:0]] or None,
        "note": "热榜只描述历史频次与遗漏，不含任何预测能力",
    }, ensure_ascii=False))


def cmd_combo(d, k, window, max_age_hours):
    rows = load(d)
    if len(rows) < 30:
        raise SystemExit("历史不足 30 期（当前 %d 期）：按铁律必须先补齐当时的热榜数据再出码，"
                         "不许退回冻结集合" % len(rows))
    ok, age, msg = freshness(rows, max_age_hours)
    if not ok:
        raise SystemExit("拒绝出码：%s" % msg)
    seg, freq, miss = score(rows, window)
    rank = sorted(range(1, 50), key=lambda x: (-freq[x], -miss[x]))
    codes = sorted(rank[:k])
    cold_tails = [t for t, _ in sorted(
        {t: sum(freq[x] for x in range(1, 50) if x % 10 == t) for t in range(10)}.items(),
        key=lambda kv: kv[1])][:2]
    covered = [x for x in codes if x % 10 in cold_tails]
    print(json.dumps({
        "ok": True, "rule": "M23-DATA-v1", "k": k, "codes": codes,
        "coverage_pct": round(k / 49 * 100, 2),
        "basis": {"draws": len(rows), "window": len(seg), "latest_issue": str(seg[-1]["issue"]),
                  "recorded": rows[-1].get("recorded"), "age_hours": age},
        "top_scores": {str(x): round(freq[x], 2) for x in rank[:k]},
        "cold_tails_avoided": cold_tails,
        "codes_in_cold_tails": covered,
        "note": "按加权热榜取前 %d 码；命中概率仍是 %d/49，期望为负" % (k, k),
    }, ensure_ascii=False))


def cmd_status(d):
    rows = load(d)
    p, _ = paths(d)
    print(json.dumps({
        "ok": True, "draws_file": p, "draws": len(rows),
        "latest": (str(rows[-1]["issue"]), rows[-1]["special"]) if rows else None,
        "ready_for_data_pick": len(rows) >= 30 and freshness(rows, 72)[0],
        "freshness": freshness(rows, 72)[2] if rows else "没有数据",
        "note": "≥30 期才能按热榜出码；不足时用冻结 23 码",
    }, ensure_ascii=False))


def cmd_set_pick(d, issue):
    """把当前热榜 23 码写入 picks.jsonl，供后续结算对照(不改冻结集合)。"""
    rows = load(d)
    if len(rows) < 30:
        raise SystemExit("历史不足 30 期，无法按热榜出码")
    seg, freq, miss = score(rows, 120)
    rank = sorted(range(1, 50), key=lambda x: (-freq[x], -miss[x]))
    codes = sorted(rank[:23])
    _, plog = paths(d)
    with open(plog, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"),
                            "issue": issue, "rule": "M23-DATA-v1", "codes": codes,
                            "basis_draws": len(rows)}, ensure_ascii=False) + "\n")
    print(json.dumps({"ok": True, "issue": issue, "codes": codes, "log": plog}, ensure_ascii=False))


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    cmd = argv[1]
    d = arg(argv, "--dir") or base_dir()
    if cmd == "record":
        cmd_record(d, arg(argv, "--issue"), nums(arg(argv, "--regular", "")), int(arg(argv, "--special", 0)))
    elif cmd == "analyze":
        cmd_analyze(d, int(arg(argv, "--window", 120) or 120))
    elif cmd == "combo":
        cmd_combo(d, int(arg(argv, "--k", 23) or 23), int(arg(argv, "--window", 120) or 120),
                  float(arg(argv, "--max-age-hours", 72) or 72))
    elif cmd == "status":
        cmd_status(d)
    elif cmd == "set-pick":
        cmd_set_pick(d, arg(argv, "--issue"))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv)