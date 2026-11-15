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
import com.wangzan101.mika.core.uistate.ActionResult
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
private const val READ_CHAT_SETTLE_DEFAULT = 500
private const val READ_CHAT_SETTLE_MIN = 100
private const val READ_CHAT_SETTLE_MAX = 3_000
private const val TAP_OCR_INDEX_MAX = 50
private const val TAP_OCR_WAIT_MAX = 5_000
private const val TAP_OCR_RETRY_STEP = 250L
private const val LONG_SHOT_DEFAULT = 6
private const val LONG_SHOT_MAX = 12
private const val LONG_SHOT_SETTLE_DEFAULT = 400
private const val LONG_SHOT_SETTLE_MAX = 3_000
private const val LONG_SHOT_PRESCROLL_MAX = 30
private const val LONG_SHOT_PRESCROLL_STEP = 220L

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
            "index" to int("Which matching line to tap, 0-based, when the same text appears several times (default 0). Read `total` in the result to see how many matched.", 0, TAP_OCR_INDEX_MAX),
            "waitMs" to int("Keep re-reading the screen while nothing matches, up to this many milliseconds, 0-$TAP_OCR_WAIT_MAX (default 0 = read once). Use it right after a tap, a page load or an animation.", 0, TAP_OCR_WAIT_MAX),
            "_forceWaitMs" to int("Debug builds only: ignore the first read on purpose to exercise the wait loop (release builds ignore it).", 0, TAP_OCR_WAIT_MAX),
        ),
        listOf("text"))

    override suspend fun execute(a: Args, ctx: ToolContext): ToolExecution {
        val wanted = a.str("text", max = TAP_OCR_MAX_TEXT)!!.trim()
        val exact = a.bool("exact", false)
        val index = a.int("index", 0, TAP_OCR_INDEX_MAX) ?: 0
        val waitMs = a.int("waitMs", 0, TAP_OCR_WAIT_MAX) ?: 0
        val regionArg = a.str("region", max = 40)
        val region = if (regionArg.isNullOrBlank()) null else parseRegion(regionArg)
            ?: return fail("invalid_region", Feedback["ocr.invalid_region"])
        // 调试探针（仅调试包）：故意忽略第一次读到的结果，用来验证等待循环。正式包里恒为关闭。
        val probeOn = PhoneDebug.allowForceWait && (
            (a.int("_forceWaitMs", 0, TAP_OCR_WAIT_MAX) ?: 0) > 0 ||
                (PhoneDebug.forceSkipProbe?.invoke() == true)
            )
        val forceMs = if (probeOn) {
            maxOf(a.int("_forceWaitMs", 0, TAP_OCR_WAIT_MAX) ?: 0, if (waitMs > 0) waitMs else 1_000)
        } else {
            0
        }
        val effectiveWait = maxOf(waitMs, forceMs)
        // 界面还在动时第一次读常常什么都没有:在 waitMs 里反复读,直到出现命中。
        val deadline = System.currentTimeMillis() + effectiveWait
        var lines: List<VisibleTextLine>? = null
        var hits: List<VisibleTextLine> = emptyList()
        var waited = 0L
        var skip = probeOn
        while (true) {
            lines = ctx.screen.readVisibleTextIn(region)
                ?: return fail("ocr_unavailable", Feedback["ocr.unavailable"])
            hits = if (skip) emptyList() else ranked(wanted, exact, lines)
            skip = false
            if (hits.isNotEmpty() || System.currentTimeMillis() >= deadline) break
            waited += TAP_OCR_RETRY_STEP
            delay(TAP_OCR_RETRY_STEP)
        }
        if (hits.isEmpty()) {
            return fail("ocr_no_match",
                Feedback.format("ocr.no_match", "text" to wanted, "nearby" to nearby(wanted, lines!!)))
        }
        if (index >= hits.size) {
            return fail("ocr_index_out_of_range",
                "only ${hits.size} line(s) matched '$wanted'; index was $index (0-based).")
        }
        val hit = hits[index]
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
                put("index", index)
                put("total", hits.size)
                if (hits.size > 1) put("alsoMatched", hits.size - 1)
                if (waited > 0) put("waitedMs", waited)
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

    /**
     * 全部命中按「该点的可能性」排序:
     * 1. 整行正好等于要找的文字优先(按钮本身),其次才是包含它的长行;
     * 2. 短的优先(通常是按钮,长的多半是正文);
     * 3. 同样长取更靠上的。
     *
     * 排序稳定,所以模型可以用 `index` 指定「第几个」来区分同名列表项。
     */
    private fun ranked(wanted: String, exact: Boolean, lines: List<VisibleTextLine>): List<VisibleTextLine> =
        lines.filter { matches(wanted, it.text, exact) }
            .sortedWith(
                compareBy<VisibleTextLine>(
                    { if (it.text.trim() == wanted) 0 else 1 },
                    { it.text.length },
                    { it.bounds.getOrElse(1) { 0 } },
                ),
            )

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
            "direction" to str("'down' (default): read newer content below. 'up': read older content above — the usual case for chat history and notification lists."),
            "settleMs" to int("How long to wait after each scroll before reading again, $READ_CHAT_SETTLE_MIN-$READ_CHAT_SETTLE_MAX ms (default $READ_CHAT_SETTLE_DEFAULT). Raise it on slow devices or when the list animates.", READ_CHAT_SETTLE_MIN, READ_CHAT_SETTLE_MAX),
            "region" to str("Optional area to read on every screen, `left,top,right,bottom` in 0–999 coordinates (default: the whole screen)."),
            "until" to str("Optional text: stop as soon as a line containing it is read, and include that line in `lines`. Use it to read back to a known landmark (a date header, `以下为新消息`, the first message you already have) instead of guessing maxScreens."),
            "match" to str("Optional filter: keep only lines containing this text (case-insensitive). Reading still scrolls and de-duplicates the whole list, so you can pull just the lines that matter (one sender, one keyword) out of a long chat without passing everything to yourself."),
        ))

    override suspend fun execute(a: Args, ctx: ToolContext): ToolExecution {
        val maxScreens = a.int("maxScreens", 1, READ_CHAT_MAX) ?: READ_CHAT_DEFAULT
        val settleMs = a.int("settleMs", READ_CHAT_SETTLE_MIN, READ_CHAT_SETTLE_MAX) ?: READ_CHAT_SETTLE_DEFAULT
        val until = a.str("until", max = TAP_OCR_MAX_TEXT)?.trim()?.takeIf { it.isNotEmpty() }
        val match = a.str("match", max = TAP_OCR_MAX_TEXT)?.trim()?.takeIf { it.isNotEmpty() }
        val down = when (val dir = a.str("direction", max = 16)?.trim()?.lowercase()) {
            null, "", "down", "newer", "next" -> true
            "up", "older", "prev", "previous" -> false
            else -> return fail("invalid_direction", "direction is 'down' or 'up', not '$dir'.")
        }
        val regionArg = a.str("region", max = 40)
        val region = if (regionArg.isNullOrBlank()) null else parseRegion(regionArg)
            ?: return fail("invalid_region", Feedback["ocr.invalid_region"])
        val perScreen = ArrayList<List<String>>()
        val seen = LinkedHashSet<String>()
        var screens = 0
        var truncated = false
        var stoppedBy: String? = null
        var total = 0
        var i = 0
        while (i < maxScreens) {
            val lines = ctx.screen.readVisibleTextIn(region) ?: return fail("ocr_unavailable", Feedback["ocr.unavailable"])
            var texts = lines.map { it.text.trim() }.filter { it.isNotEmpty() }
            // until:读到标志行就把它一起收下并停,不再往下/往上翻。
            if (until != null) {
                val hitAt = texts.indexOfFirst { it.contains(until, ignoreCase = true) }
                if (hitAt >= 0) {
                    texts = texts.take(hitAt + 1)
                    stoppedBy = "until"
                }
            }
            var added = 0
            for (t in texts) {
                if (!seen.add(t)) continue
                total += t.length
                added++
            }
            perScreen += texts
            screens++
            if (stoppedBy != null) break
            val full = total > READ_CHAT_CHARS
            if (added == 0 || full) { truncated = truncated || full; break }
            if (i == maxScreens - 1) { truncated = true; break }
            ctx.screen.scroll(null, null, down = down)
            delay(settleMs.toLong())
            i++
        }
        // 往下读时屏序就是时间序;往上读时先读到的那屏是较新的内容,屏序要倒过来才是顺序。
        val ordered = if (down) perScreen else perScreen.asReversed()
        val merged = ArrayList<String>()
        val dedupe = HashSet<String>()
        var keptChars = 0
        outer@ for (screen in ordered) {
            for (t in screen) {
                if (!dedupe.add(t)) continue
                if (keptChars + t.length > READ_CHAT_CHARS) { truncated = true; break@outer }
                keptChars += t.length
                merged += t
            }
        }
        // match:滚完整个列表再筛,只把含关键词的行交回去——长聊天记录里这一点最省 token。
        val kept = if (match == null) merged else merged.filter { it.contains(match, ignoreCase = true) }
        return ok {
            put("screens", screens)
            put("direction", if (down) "down" else "up")
            put("lines", JsonArray(kept.map { kotlinx.serialization.json.JsonPrimitive(it) }))
            put("truncated", truncated)
            // 降级模式:翻的是用户自己的屏幕,他看得见、也可能同时在动
            if (ctx.screen.degradedScreen) put("degraded", true)
            stoppedBy?.let { put("stoppedBy", it) }
            if (match != null) {
                put("matched", kept.size)
                put("dropped", merged.size - kept.size)
            }
            if (kept.isEmpty()) {
                put("hint", if (match != null) {
                    "No line contained \"$match\". Lines were read ($screens screens) but all were filtered out; retry without `match` to see them."
                } else {
                    Feedback["read_chat.empty"]
                })
            }
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
            "startFrom" to str("Where to start: 'current' (default), 'top' or 'bottom'. The page is scrolled to that edge first, so a list someone left mid-way still comes out complete."),
            "settleMs" to int("Wait this long after positioning and before the first frame, 0-$LONG_SHOT_SETTLE_MAX ms (default $LONG_SHOT_SETTLE_DEFAULT). Raise it for slow pages.", 0, LONG_SHOT_SETTLE_MAX),
            "savePath" to str("Optional new PNG path under /workspace: save the long image there, then share_file it to the user. Very tall pages are split into <name>-1.png, <name>-2.png …"),
        ))

    override fun readOnly(args: kotlinx.serialization.json.JsonObject) = "savePath" !in args

    override suspend fun execute(a: Args, ctx: ToolContext): ToolExecution {
        val maxScreens = a.int("maxScreens", 1, LONG_SHOT_MAX) ?: LONG_SHOT_DEFAULT
        val settleMs = a.int("settleMs", 0, LONG_SHOT_SETTLE_MAX) ?: LONG_SHOT_SETTLE_DEFAULT
        val startFrom = when (val s = a.str("startFrom", max = 12)?.trim()?.lowercase()) {
            null, "", "current", "here" -> "current"
            "top", "head", "begin", "beginning" -> "top"
            "bottom", "end", "tail" -> "bottom"
            else -> return fail("invalid_start_from", "startFrom is 'current', 'top' or 'bottom', not '$s'.")
        }
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
        // 先把页面挪到指定的一端:滚到"这一下没让界面变化"为止,说明到边了。
        var preScrolls = 0
        var atEdge = false
        if (startFrom != "current") {
            val down = startFrom == "bottom"
            while (preScrolls < LONG_SHOT_PRESCROLL_MAX) {
                val r = ctx.screen.scroll(null, null, down = down)
                preScrolls++
                if (r is ActionResult.Failed) break
                if (r is ActionResult.Ok && r.changed == false) { atEdge = true; break }
                delay(LONG_SHOT_PRESCROLL_STEP)
            }
        }
        if (settleMs > 0) delay(settleMs.toLong())
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
                put("startFrom", startFrom)
                if (preScrolls > 0) put("preScrolls", preScrolls)
                // 降级模式:每帧之间要等主屏截图的最小间隔,比虚拟屏慢得多,顺手说清楚在哪拍的
                if (ctx.screen.degradedScreen) put("degraded", true)
                if (startFrom != "current") put("atEdge", atEdge)
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
