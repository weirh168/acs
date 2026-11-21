"""福运堂八字命理插件 · fuyuntang-bazi

给 Hermes（或任何加载本目录的智能体）提供三件事：
  1. bazi_paipan   —— 公历/农历 → 四柱 + 大运 + 起运（lunar-python，立春法 + 真太阳时）
  2. mingli_engine —— 八字 → 145 函数引擎的判读摘要（强弱/格局/喜忌/婚姻/事业/健康/应期）
  3. mingli_rules  —— 按主题读取本插件 references/ 下的规则原文

依赖：lunar-python（脚本 scripts/bazi.py 与 engine.py 需要）。
没装的话 bazi_paipan 会返回明确提示，不会静默失败。
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).resolve().parent
PLUGIN_DIR = SCRIPTS_DIR.parent
REFS_DIR = PLUGIN_DIR / "references"
VENDOR_DIR = SCRIPTS_DIR / "vendor"

_TOOLSET = "mingli"

for _p in (str(SCRIPTS_DIR / "vendor"), str(SCRIPTS_DIR)):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)


def _ensure_scripts_on_path() -> None:
    for p in (str(VENDOR_DIR), str(SCRIPTS_DIR)):
        if os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)


def _need_lunar() -> bool:
    import importlib.util
    if "lunar_python" in sys.modules:
        return True
    try:
        return importlib.util.find_spec("lunar_python") is not None
    except (ImportError, ValueError):
        return False


def _err(msg: str) -> str:
    return json.dumps({"ok": False, "error": msg}, ensure_ascii=False)


def _ok(payload: dict[str, Any]) -> str:
    payload["ok"] = True
    return json.dumps(payload, ensure_ascii=False, indent=1, default=str)


# ─────────────────────────── 工具 1：排盘 ───────────────────────────

PAIPAN_SCHEMA = {
    "name": "bazi_paipan",
    "description": (
        "八字排盘：按公历或农历出生时间排出四柱、大运、起运岁数与交运年。"
        "立春法定年柱月柱，可传经度做真太阳时校正。"
        "性别用于定大运顺逆（阳男阴女顺排，阴男阳女逆排）。"
        "返回 JSON：四柱、农历、起运、顺逆、八步大运。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "year": {"type": "integer", "description": "出生年，如 1985"},
            "month": {"type": "integer", "description": "出生月 1-12"},
            "day": {"type": "integer", "description": "出生日 1-31"},
            "hour": {"type": "integer", "description": "出生时 0-23"},
            "minute": {"type": "integer", "description": "出生分 0-59，默认 0"},
            "calendar": {
                "type": "string",
                "enum": ["solar", "lunar"],
                "description": "solar=公历（默认），lunar=农历",
            },
            "gender": {
                "type": "string",
                "enum": ["male", "female"],
                "description": "male=乾造，female=坤造",
            },
            "longitude": {
                "type": "number",
                "description": "出生地经度（可选），用于真太阳时校正，如广州 113.3",
            },
        },
        "required": ["year", "month", "day", "hour", "gender"],
        "additionalProperties": False,
    },
}


def handle_bazi_paipan(args: dict[str, Any], **_kw) -> str:
    if not _need_lunar():
        return _err("缺少依赖 lunar-python，请先 pip install lunar-python")
    try:
        year = int(args["year"])
        month = int(args["month"])
        day = int(args["day"])
        hour = int(args["hour"])
        minute = int(args.get("minute") or 0)
    except (KeyError, TypeError, ValueError) as e:
        return _err(f"日期参数不合法：{e}")

    calendar = (args.get("calendar") or "solar").lower()
    gender = (args.get("gender") or "").lower()
    if gender not in {"male", "female"}:
        return _err("gender 必须是 male 或 female")
    lon = args.get("longitude")

    _ensure_scripts_on_path()
    try:
        import bazi
    except Exception as e:  # pragma: no cover
        return _err(f"无法加载排盘脚本：{e}")

    try:
        if calendar == "lunar":
            res = bazi.bazi_from_lunar(year, month, day, hour, minute, lon)
            yg, mg, dg, sg, sc, solar, _lunar = res
            sy, sm, sd = solar.getYear(), solar.getMonth(), solar.getDay()
        else:
            res = bazi.bazi_from_solar(year, month, day, hour, minute, lon)
            yg, mg, dg, sg, sc, lunar = res
            sy, sm, sd = year, month, day
            solar = None

        dayun = bazi.calc_dayun(sy, sm, sd, hour, minute, gender == "male")
    except Exception as e:
        return _err(f"排盘失败：{e}")

    out: dict[str, Any] = {
        "四柱": f"{yg} {mg} {dg} {sg}",
        "年柱": yg, "月柱": mg, "日柱": dg, "时柱": sg,
        "时辰": sc[0] if isinstance(sc, (list, tuple)) else sc,
        "性别": "乾造" if gender == "male" else "坤造",
        "历法": "农历" if calendar == "lunar" else "公历",
        "起运": dayun.get("起运"),
        "顺逆": dayun.get("顺逆"),
        "大运": [
            {"干支": f"{g}{z}", "起始": s, "结束": e}
            for g, z, s, e in dayun.get("大运", [])
        ],
    }
    if solar is not None:
        out["对应公历"] = f"{solar.getYear()}-{solar.getMonth():02d}-{solar.getDay():02d}"
    return _ok(out)


# ─────────────────────────── 工具 2：引擎判读 ───────────────────────────

ENGINE_SCHEMA = {
    "name": "mingli_engine",
    "description": (
        "命理引擎判读：给一个八字四柱字符串（如 '乙丑 乙酉 乙丑 壬午'），"
        "返回 145 函数引擎的核心结论——身强弱、喜用忌神、格局评分、"
        "婚姻、事业、健康、学历、财富等级、应期等。"
        "输出是结构化 JSON，供进一步叙述使用。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "bazi": {
                "type": "string",
                "description": "四柱，用空格分隔，如 '乙丑 乙酉 乙丑 壬午'",
            },
            "age": {"type": "integer", "description": "当前虚岁或周岁（可选）"},
            "gender": {"type": "string", "enum": ["male", "female"]},
            "modules": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "要跑的模块，可选：core(默认全量简版) / marriage / career / "
                    "health / education / wealth / yingqi"
                ),
            },
        },
        "required": ["bazi"],
        "additionalProperties": False,
    },
}


def handle_mingli_engine(args: dict[str, Any], **_kw) -> str:
    if not _need_lunar():
        return _err("缺少依赖 lunar-python，请先 pip install lunar-python")
    bazi_str = (args.get("bazi") or "").strip()
    if len(bazi_str.replace(" ", "")) < 8:
        return _err("bazi 需要四柱八个字，如 '乙丑 乙酉 乙丑 壬午'")

    gender = (args.get("gender") or "male").lower()
    age = args.get("age")
    mods = args.get("modules") or ["core"]

    _ensure_scripts_on_path()
    try:
        import engine
    except Exception as e:  # pragma: no cover
        return _err(f"无法加载引擎：{e}")

    result: dict[str, Any] = {"八字": bazi_str}

    def safe(label, fn, *a, **kw):
        try:
            result[label] = fn(*a, **kw)
        except Exception as e:
            result[label] = {"error": str(e)}

    try:
        if "core" in mods:
            safe("引擎总览", engine.analyze, bazi_str, **(({"age": age} if age else {})))
        if "marriage" in mods:
            safe("婚姻", engine.marriage_analyze, bazi_str, gender=gender)
            safe("婚姻结局", engine.hunyin_jieju, bazi_str)
            safe("婚姻次数", engine.hunyin_cishu, bazi_str)
        if "career" in mods:
            safe("事业", engine.career_analyze, bazi_str)
        if "health" in mods:
            safe("健康", engine.health_analyze, bazi_str)
        if "education" in mods:
            safe("学历", engine.education_eval, bazi_str)
        if "wealth" in mods:
            safe("财富", engine.caifu_shangxian, bazi_str)
        if "yingqi" in mods:
            safe("应期", engine.yingqi_3year, bazi_str)
    except Exception as e:  # pragma: no cover
        return _err(f"引擎执行失败：{e}")

    return _ok(result)


# ─────────────────────────── 工具 3：规则库 ───────────────────────────

RULES_SCHEMA = {
    "name": "mingli_rules",
    "description": (
        "读取福运堂命理规则库：列出全部规则文件，或按主题返回原文。"
        "主题包括 排盘、叙事输出、五行格局、盲派、古籍、素水、婚姻、健康、合规等。"
        "写分析前先取对应规则，照规则写，不要即兴发挥。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "规则文件名（可不带 .md）或关键词，如 'mingli-life-narrative'、'输出格式'。留空则列出全部。",
            },
            "max_chars": {
                "type": "integer",
                "description": "最多返回多少字符，默认 12000。",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
}


def handle_mingli_rules(args: dict[str, Any], **_kw) -> str:
    if not REFS_DIR.is_dir():
        return _err(f"规则目录不存在：{REFS_DIR}")

    files = sorted(p for p in REFS_DIR.glob("*.md"))
    topic = (args.get("topic") or "").strip()
    limit = int(args.get("max_chars") or 12000)

    if not topic:
        return _ok({
            "规则文件": [
                {"名称": p.stem, "字节": p.stat().st_size} for p in files
            ],
            "提示": "传 topic 取原文，如 topic='mingli-life-narrative'",
        })

    needle = topic.lower()
    hit = [p for p in files if needle in p.stem.lower()]
    if not hit:
        return _err(
            "未匹配到规则文件。可选：" + "、".join(p.stem for p in files)
        )

    path = hit[0]
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return _err(f"读取失败：{e}")

    truncated = len(text) > limit
    return _ok({
        "规则": path.stem,
        "截断": truncated,
        "内容": text[:limit],
    })


# ─────────────────────────── 注册 ───────────────────────────

_TOOLS = (
    ("bazi_paipan", PAIPAN_SCHEMA, handle_bazi_paipan, "🧮"),
    ("mingli_engine", ENGINE_SCHEMA, handle_mingli_engine, "📊"),
    ("mingli_rules", RULES_SCHEMA, handle_mingli_rules, "📜"),
)


def check_requirements() -> bool:
    """引擎与排盘都需要 lunar-python；规则库单独可用。"""
    return True


def register(ctx) -> None:
    for name, schema, handler, emoji in _TOOLS:
        ctx.register_tool(
            name=name,
            toolset=_TOOLSET,
            schema=schema,
            handler=handler,
            check_fn=check_requirements,
            emoji=emoji,
        )
    logger.info("fuyuntang-bazi: 已注册 %d 个工具（toolset=%s）", len(_TOOLS), _TOOLSET)
