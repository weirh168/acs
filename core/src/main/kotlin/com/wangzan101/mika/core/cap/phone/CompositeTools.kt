package com.wangzan101.mika.core.cap.phone

import com.wangzan101.mika.core.prompt.Feedback
import com.wangzan101.mika.core.prompt.Prompts
import com.wangzan101.mika.core.risk.GateTarget
import com.wangzan101.mika.core.tool.Args
import com.wangzan101.mika.core.tool.Risk
import com.wangzan101.mika.core.tool.ToolContext
import com.wangzan101.mika.core.tool.ToolDef
import com.wangzan101.mika.core.tool.ToolExecution
import com.wangzan101.mika.core.tool.Verb
import com.wangzan101.mika.core.tool.bool
import com.wangzan101.mika.core.tool.fail
import com.wangzan101.mika.core.tool.int
import com.wangzan101.mika.core.tool.ok
import com.wangzan101.mika.core.tool.str
import com.wangzan101.mika.core.uistate.VisibleTextLine
import com.wangzan101.mika.core.uistate.action
import com.wangzan101.mika.core.uistate.screen
import com.wangzan101.mika.core.uistate.lastOrSnapshot
import com.wangzan101.mika.core.uistate.toPx
import kotlinx.coroutines.delay
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

private const val TAP_OCR_MAX_TEXT = 200

/** 解析 `left,top,right,bottom`(0–999);不合法返回 null。 */
private fun parseRegion(raw: String?): List<Int>? {
    val text = raw?.trim().orEmpty()
    if (text.isEmpty()) return null
    val parts = text.split(',').map { it.trim().toIntOrNull() ?: return null }
    if (parts.size != 4) return null
    val (l, t, r, b) = parts
    if (l < 0 || t < 0 || r > 999 || b > 999) return null
    if (l >= r || t >= b) return null
    return parts
}
private const val READ_CHAT_DEFAULT = 5
private const val READ_CHAT_MAX = 20
private const val READ_CHAT_CHARS = 20_000
private const val LONG_SHOT_DEFAULT = 6
private const val LONG_SHOT_MAX = 12

/**
 * 按屏上的文字点一下:走本机 OCR,不依赖无障碍节点。
 *
 * 什么时候用:控件是画出来的(Canvas、游戏、Flutter/RN 表面),树里没有节点,`tap` 的 ref 指不到;
 * 或者 [[observe]] 的 `ocrOnly` 里已经给出了要点的文字。
 */
internal object TapOcr : PhoneTool {
    override val verb = Verb.Tap
    override val label = "按文字点击"
    override val risk = Risk.External
    override val gateTarget = GateTarget.Tap
    override val reportsEffect = true
    override val showsScreenAfter = true
    override val def = ToolDef("phone_tap_ocr",
        Prompts.tool("phone_tap_ocr"),
        mapOf(
            "text" to str("Text to tap, as it appears on screen (OCR). The line's center is tapped."),
            "exact" to bool("Only accept a line equal to the text (default false: a line containing it is enough)."),
            "region" to str("Optional area to look at, `left,top,right,bottom` in 0–999 coordinates (default: the whole screen)."),
        ),
        listOf("text"))

    override suspend fun execute(a: Args, ctx: ToolContext): ToolExecution {
        val wanted = a.str("text", max = TAP_OCR_MAX_TEXT)!!.trim()
        val exact = a.bool("exact", false)
        val regionArg = a.str("region", max = 40)
        val region = if (regionArg.isNullOrBlank()) null else parseRegion(regionArg)
            ?: return fail("invalid_region", Feedback["ocr.invalid_region"])
        val lines = ctx.screen.readVisibleTextIn(region)
            ?: return fail("ocr_unavailable", Feedback["ocr.unavailable"])
        val hit = best(wanted, exact, lines)
            ?: return fail("ocr_no_match",
                Feedback.format("ocr.no_match", "text" to wanted, "nearby" to nearby(wanted, lines)))
        val s = ctx.lastOrSnapshot()
        val cx = (hit.bounds[0] + hit.bounds[2]) / 2
        val cy = (hit.bounds[1] + hit.bounds[3]) / 2
        val base = ctx.action(ctx.screen.tapXY(toPx(cx, s.width), toPx(cy, s.height)))
        // 在动作结果上补一句「匹配到的是哪一行」,模型据此判断点得对不对
        return ToolExecution(
            buildJsonObject {
                base.content.forEach { (k, v) -> put(k, v) }
                put("matchedText", hit.text)
                put("x", cx); put("y", cy)
                val others = lines.count { matches(wanted, it.text, exact) } - 1
                if (others > 0) put("alsoMatched", others)
            },
            image = null, changed = base.changed, outcome = base.outcome, frame = base.frame,
            images = base.images, record = base.record, screenElements = base.screenElements,
            imageIds = base.imageIds, observations = base.observations, place = base.place, waitMs = base.waitMs,
        )
    }

    private fun matches(wanted: String, line: String, exact: Boolean): Boolean {
        val t = line.trim()
        if (t.isEmpty()) return false
        return if (exact) t == wanted else t.contains(wanted, ignoreCase = true)
    }

    /** 先找完全相等的;没有就找包含的,取最短的一行(通常是最精确的那个按钮),同样长取更靠上的。 */
    private fun best(wanted: String, exact: Boolean, lines: List<VisibleTextLine>): VisibleTextLine? {
        val hits = lines.filter { matches(wanted, it.text, exact) }
        if (hits.isEmpty()) return null
        return hits.minWithOrNull(compareBy<VisibleTextLine>({ it.text.length }, { it.bounds.getOrElse(1) { 0 } }))
    }

    /** 没找到时给几行最像的:先看共同前缀/长度差,最多三行。 */
    private fun nearby(wanted: String, lines: List<VisibleTextLine>): String {
        val scored = lines.filter { it.text.isNotBlank() }
            .map { it to commonPrefix(wanted.lowercase(), it.text.lowercase()) }
            .sortedByDescending { it.second }
            .take(3)
            .map { it.first.text }
        return if (scored.isEmpty()) "(nothing readable on screen; try phone_observe)" else scored.joinToString(" / ")
    }

    private fun commonPrefix(a: String, b: String): Int {
        var i = 0
        while (i < a.length && i < b.length && a[i] == b[i]) i++
        return i
    }
}

/**
 * 把一屏一屏的文字接成一段:边读边往下滚,直到没有新文字或用完帧数。
 *
 * 用在长聊天记录、长列表、长通知页:比逐屏 `observe` 省得多,也不依赖树。
 */
internal object ReadChat : PhoneTool {
    override val verb = Verb.PhoneExtract
    override val label = "读长列表"
    override val risk = Risk.Read
    override val def = ToolDef("phone_read_chat",
        Prompts.tool("phone_read_chat", "default" to READ_CHAT_DEFAULT, "max" to READ_CHAT_MAX),
        mapOf(
            "maxScreens" to int("How many screens to scroll through, 1-$READ_CHAT_MAX (default $READ_CHAT_DEFAULT).", 1, READ_CHAT_MAX),
            "region" to str("Optional area to read on every screen, `left,top,right,bottom` in 0–999 coordinates (default: the whole screen)."),
        ))

    override suspend fun execute(a: Args, ctx: ToolContext): ToolExecution {
        val maxScreens = a.int("maxScreens", 1, READ_CHAT_MAX) ?: READ_CHAT_DEFAULT
        val regionArg = a.str("region", max = 40)
        val region = if (regionArg.isNullOrBlank()) null else parseRegion(regionArg)
            ?: return fail("invalid_region", Feedback["ocr.invalid_region"])
        val seen = LinkedHashSet<String>()
        var screens = 0
        var truncated = false
        var total = 0
        var i = 0
        while (i < maxScreens) {
            val lines = ctx.screen.readVisibleTextIn(region) ?: return fail("ocr_unavailable", Feedback["ocr.unavailable"])
            var added = 0
            for (line in lines) {
                val t = line.text.trim()
                if (t.isEmpty() || !seen.add(t)) continue
                total += t.length
                added++
                if (total > READ_CHAT_CHARS) { truncated = true; break }
            }
            screens++
            if (added == 0 || truncated) break
            if (i == maxScreens - 1) { truncated = true; break }
            ctx.screen.scroll(null, null, down = true)
            delay(500)
            i++
        }
        return ok {
            put("screens", screens)
            put("lines", JsonArray(seen.map { kotlinx.serialization.json.JsonPrimitive(it) }))
            put("truncated", truncated)
            if (seen.isEmpty()) put("hint", Feedback["read_chat.empty"])
        }
    }
}

/**
 * 长截图:滚一屏截一帧、按内容锚点拼起来。可以竖着拍(默认)也可以横着拍(宽表格、代码、时间轴)。
 * 页面太长时按 8000 像素切段存盘;中途被弹窗/遮罩挡住会停下并说明。
 */
internal object LongScreenshot : PhoneTool {
    override val verb = Verb.Screenshot
    override val label = "长截图"
    override val risk = Risk.Read
    override val def = ToolDef("phone_long_screenshot",
        Prompts.tool("phone_long_screenshot", "default" to LONG_SHOT_DEFAULT, "max" to LONG_SHOT_MAX),
        mapOf(
            "maxScreens" to int("How many screens to stitch at most, 1-$LONG_SHOT_MAX (default $LONG_SHOT_DEFAULT).", 1, LONG_SHOT_MAX),
            "direction" to str("'vertical' (default, scroll down) or 'horizontal' (scroll sideways: wide tables, code, timelines)."),
            "savePath" to str("Optional new PNG path under /workspace: save the long image there, then share_file it to the user. Very tall pages are split into <name>-1.png, <name>-2.png …"),
        ))

    override fun readOnly(args: kotlinx.serialization.json.JsonObject) = "savePath" !in args

    override suspend fun execute(a: Args, ctx: ToolContext): ToolExecution {
        val maxScreens = a.int("maxScreens", 1, LONG_SHOT_MAX) ?: LONG_SHOT_DEFAULT
        val horizontal = when (val dir = a.str("direction", max = 16)?.trim()?.lowercase()) {
            null, "", "vertical", "down" -> false
            "horizontal", "sideways", "right" -> true
            else -> return fail("invalid_direction", "direction is 'vertical' or 'horizontal', not '$dir'.")
        }
        val savePath = a.str("savePath", max = 4096)
        if (savePath == null && !ctx.config.visionEnabled)
            return fail("save_path_required", Feedback["long_shot.save_path_required"])
        if (savePath != null && ctx.config.saveScreenshot == null)
            return fail("screenshot_save_unavailable", Feedback["screenshot_save_unavailable"])
        val shot = ctx.screen.longShot(maxScreens, horizontal)
            ?: return fail("long_screenshot_unavailable", Feedback["long_shot.unavailable"])
        if (shot.segmented && savePath == null)
            return fail("save_path_required", Feedback["long_shot.segmented_needs_path"])

        val saved = mutableListOf<String>()
        if (savePath != null) {
            val save = ctx.config.saveScreenshot!!
            try {
                if (shot.segments.size == 1) {
                    saved += save(savePath, shot.segments.first())
                } else {
                    shot.segments.forEachIndexed { i, bytes ->
                        saved += save(segmentPath(savePath, i + 1), bytes)
                    }
                }
            } catch (e: com.wangzan101.mika.core.workspace.SandboxError) {
                return fail(e.code, e.message ?: e.code, e.recoverable)
            }
        }
        return ToolExecution(
            buildJsonObject {
                put("ok", true)
                put("width", shot.width); put("height", shot.height); put("screens", shot.screens)
                put("direction", if (horizontal) "horizontal" else "vertical")
                if (shot.segments.size > 1) put("segments", shot.segments.size)
                if (shot.overlaps.isNotEmpty()) put("overlaps", shot.overlaps.joinToString(","))
                if (saved.isNotEmpty()) put("saved", saved.joinToString(", "))
                shot.blocked?.let {
                    put("blocked", it)
                    put("hint", Feedback.format("long_shot.blocked", "why" to it))
                }
            },
            image = shot.segments.first().takeIf { savePath == null && ctx.config.visionEnabled },
            frame = shot.segments.first(),
        )
    }

    /** `a.png` → `a-1.png`、`a-2.png`;没有 .png 后缀时照加。 */
    private fun segmentPath(path: String, index: Int): String {
        val dot = path.lastIndexOf(".png")
        return if (dot >= 0) path.substring(0, dot) + "-" + index + path.substring(dot) else "$path-$index"
    }
}
