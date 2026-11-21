#!/usr/bin/env python3
"""预测回测记录（原插件引用了 predict_record 但没带文件，这里补齐同名 API）。"""
import json
import os
import uuid
from datetime import datetime

PATH = os.environ.get("FUYUNTANG_PREDICT_PATH") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "predict_record.json")
if not os.access(os.path.dirname(PATH), os.W_OK):
    PATH = os.path.join(os.getcwd(), "predict_record.json")


def _load():
    if not os.path.exists(PATH):
        return []
    try:
        return json.load(open(PATH, encoding="utf-8"))
    except Exception:
        return []


def _save(rows):
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)


def add_prediction(bazi=None, item=None, expect=None, deadline=None, **kw):
    if not (bazi and item and expect):
        return {"ok": False, "error": "需要 bazi、item、expect"}
    rows = _load()
    row = {"id": uuid.uuid4().hex[:8], "bazi": bazi, "item": item, "expect": expect,
           "deadline": deadline, "created": datetime.now().isoformat(timespec="seconds"),
           "status": "pending", "result": None}
    rows.append(row)
    _save(rows)
    return {"ok": True, "record": row, "total": len(rows), "path": PATH}


def verify_prediction(prediction_id=None, result=None, **kw):
    rows = _load()
    for row in rows:
        if row["id"] == prediction_id:
            row["status"] = "verified"
            row["result"] = result
            row["verified_at"] = datetime.now().isoformat(timespec="seconds")
            _save(rows)
            return {"ok": True, "record": row}
    return {"ok": False, "error": "未找到该 id"}


def get_stats(**kw):
    rows = _load()
    pend = [r for r in rows if r.get("status") == "pending"]
    done = [r for r in rows if r.get("status") == "verified"]
    return {"ok": True, "总计": len(rows), "待验": len(pend), "已验": len(done),
            "待验清单": pend[-20:], "路径": PATH}


def get_overdue(now=None, **kw):
    now = now or datetime.now().isoformat()
    rows = [r for r in _load() if r.get("status") == "pending" and r.get("deadline") and r["deadline"] < now]
    return {"ok": True, "过期": rows}
