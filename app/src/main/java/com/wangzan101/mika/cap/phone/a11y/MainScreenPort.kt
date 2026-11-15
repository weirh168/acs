package com.wangzan101.mika.cap.phone.a11y

import android.accessibilityservice.AccessibilityService
import com.wangzan101.mika.core.cap.phone.UserPresence
import android.graphics.Bitmap
import android.graphics.Path
import android.graphics.Rect
import android.os.Bundle
import android.util.Log
import android.view.Display
import android.view.accessibility.AccessibilityNodeInfo
import com.wangzan101.mika.core.uistate.ActionResult
import com.wangzan101.mika.core.uistate.ScreenSnapshot
import com.wangzan101.mika.core.uistate.SystemActionResult
import com.wangzan101.mika.core.uistate.SystemAction
import com.wangzan101.mika.core.uistate.VisibleTextLine
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream

/**
 * 降级端口:内置助手连不上时,直接用无障碍操作**用户主屏**——读窗口、截图、认字,以及点击、滑动、输入、开 App。
 *
 * 和 [AndroidScreen] 的区别:那块屏是 Mika 自己建的虚拟屏,动作走内置助手的 shell 通道;没有助手时既没有虚拟屏也没有
 * shell,所以这里退到 `Display.DEFAULT_DISPLAY` + 无障碍手势/节点动作 + `Intent` 启动。开 App 会真的开在用户主屏上。
 *
 * 只在用户打开「没有内置助手时读我的主屏」并且无障碍服务在的时候才会被接上(见 TaskRun 的 acquire)。
 * 拍照、录屏、系统命令、多用户等需要 shell 的能力一律不可用,按具体能力报错而不是假装做了。
 */
internal class MainScreenPort(
    private val a11y: ScreenAccessibility,
    private val width: Int,
    private val height: Int,
) : com.wangzan101.mika.core.uistate.ScreenPort {

    /** 这就是降级模式本身:读写的都是用户自己的主屏。 */
    override val degradedScreen: Boolean get() = true

    private val ids = NodeIds()
    private val counter = java.util.concurrent.atomic.AtomicInteger()

    init {
        // 第一次在这个进程里进入降级时提示一句:用户得知道 Mika 现在读的是他自己的屏幕
        if (NOTICE_SHOWN.compareAndSet(false, true)) {
            runCatching {
                android.os.Handler(android.os.Looper.getMainLooper()).post {
                    android.widget.Toast.makeText(
                        a11y, "Mika 正在读取你的主屏（降级模式：内置助手未连接）", android.widget.Toast.LENGTH_LONG,
                    ).show()
                }
            }
        }
    }

    private fun nextId(): String = "p${counter.incrementAndGet()}"

    private fun windows() = a11y.windowsOn(Display.DEFAULT_DISPLAY)

    // ---------- 读 ----------

    override suspend fun snapshot(): ScreenSnapshot = capture(register = true)

    override suspend fun peek(): ScreenSnapshot = capture(register = false)

    private suspend fun capture(register: Boolean): ScreenSnapshot = withContext(Dispatchers.IO) {
        val read = runCatching { ScreenReader.read(windows(), width, height) }.getOrNull()
            ?: return@withContext ScreenSnapshot(nextId(), null, emptyList(), width, height, hasWindow = false)
        // 用户主屏上也有 Mika 自己的浮层(胶囊、小窗):读用户屏幕时把它们去掉,免得模型把浮层当内容
        val own = a11y.packageName
        val entries = read.entries.filter { it.node.packageName?.toString() != own }
        val topPackage = read.topPackage?.takeIf { it != own }
        val snap = NodeSnapshot(nextId(), entries)
        if (register) ids.put(snap)
        ScreenSnapshot(
            snapshotId = snap.id,
            packageName = topPackage,
            elements = entries.map { it.element },
            width = width,
            height = height,
            hasWindow = entries.isNotEmpty(),
            windows = read.windows,
        )
    }

    override suspend fun screenshotPng(): ByteArray? = withContext(Dispatchers.IO) {
        when (val shot = runCatching { a11y.takeMainScreenshot() }.getOrNull()) {
            is ScreenAccessibility.MainShot.Ok -> try {
                ByteArrayOutputStream().use { out ->
                    shot.bitmap.compress(Bitmap.CompressFormat.PNG, 100, out)
                    out.toByteArray()
                }
            } catch (e: Throwable) {
                Log.w("MainScreenPort", "encode failed", e)
                null
            } finally {
                shot.bitmap.recycle()
            }
            ScreenAccessibility.MainShot.Secure -> null
            is ScreenAccessibility.MainShot.Failed -> {
                Log.w("MainScreenPort", "screenshot failed: ${shot.code}")
                null
            }
            null -> null
        }
    }

    override suspend fun readVisibleText(): List<VisibleTextLine>? = withContext(Dispatchers.IO) {
        val shot = runCatching { a11y.takeMainScreenshot() }.getOrNull()
        if (shot !is ScreenAccessibility.MainShot.Ok) return@withContext null
        try {
            PhoneOcr.read(shot.bitmap)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            Log.w("MainScreenPort", "ocr failed", e)
            null
        }
    }

    override suspend fun readVisibleTextIn(region: List<Int>?): List<VisibleTextLine>? = withContext(Dispatchers.IO) {
        if (region == null || region.size != 4) return@withContext readVisibleText()
        val shot = runCatching { a11y.takeMainScreenshot() }.getOrNull()
        if (shot !is ScreenAccessibility.MainShot.Ok) return@withContext null
        val frame = shot.bitmap
        val cropped = cropRegion(frame, region)
        if (cropped !== frame) frame.recycle()
        try {
            cropped?.let { PhoneOcr.read(it) }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            Log.w("MainScreenPort", "ocr(region) failed", e)
            null
        }
    }

    private fun cropRegion(frame: Bitmap, region: List<Int>): Bitmap? {
        fun px(n: Int, size: Int) = ((n.coerceIn(0, 999) * (size - 1)) / 999.0).toInt()
        val left = px(region[0], frame.width)
        val top = px(region[1], frame.height)
        val right = px(region[2], frame.width)
        val bottom = px(region[3], frame.height)
        if (right - left < 2 || bottom - top < 2) return null
        return runCatching { Bitmap.createBitmap(frame, left, top, right - left, bottom - top) }.getOrNull()
    }

    override suspend fun listApps(): List<Pair<String, String>> = withContext(Dispatchers.IO) {
        runCatching { launchableApps(a11y.packageManager, a11y.packageName) }.getOrDefault(emptyList())
    }

    // ---------- 动作 ----------

    private fun entryOf(ref: String, snapshotId: String): NodeEntry? {
        val lookup = ids.lookup(ref, snapshotId)
        return when (lookup) {
            is NodeIds.Lookup.Current -> lookup.entry
            is NodeIds.Lookup.Old -> lookup.entry
            NodeIds.Lookup.Unknown -> null
        }
    }

    override suspend fun tapRef(ref: String, snapshotId: String): ActionResult {
        val entry = entryOf(ref, snapshotId) ?: return ActionResult.Failed("ref_expired")
        val clicked = runCatching { entry.node.performAction(AccessibilityNodeInfo.ACTION_CLICK) }.getOrDefault(false)
        if (clicked) return ActionResult.Ok(changed = null)
        val bounds = Rect().also { runCatching { entry.node.getBoundsInScreen(it) } }
        if (bounds.width() <= 0 || bounds.height() <= 0) return ActionResult.Failed(NOT_TAPPABLE, HINT_TAP)
        return tapAt(bounds.exactCenterX(), bounds.exactCenterY())
    }

    override suspend fun tapXY(x: Int, y: Int): ActionResult = tapAt(x.toFloat(), y.toFloat())

    override suspend fun doubleTapXY(x: Int, y: Int): ActionResult =
        tapAt(x.toFloat(), y.toFloat(), count = 2)

    /**
     * 动手前先让一让:用户刚碰过屏就等一会儿(最多 [UserPresence.MAX_WAIT_MS]),
     * 免得两边同时操作把要点的东西滑走。返回等了多少毫秒。
     */
    private suspend fun waitForUser(): Long =
        UserPresence.awaitIdle(
            lastTouchAt = { if (ScreenAccessibility.userTouchedAt() <= 0L) 0L else ScreenAccessibility.userTouchedAt() },
            clock = { android.os.SystemClock.elapsedRealtime() },
        )

    /** 记下"接下来这段是我们自己的手势",触摸事件不算用户碰的。 */
    private fun markSelf(ms: Long) {
        ScreenAccessibility.markSelfInput(android.os.SystemClock.elapsedRealtime() + ms)
    }

    private suspend fun tapAt(x: Float, y: Float, count: Int = 1): ActionResult {
        val waited = waitForUser()
        markSelf(600L + count * 120L)
        val ok = runCatching { a11y.taps(Display.DEFAULT_DISPLAY, x, y, count, 0L, 80L) }.getOrDefault(false)
        return if (ok) ActionResult.Ok(changed = null, hint = waitedHint(waited)) else ActionResult.Failed(TAP_FAILED, HINT)
    }

    /** 等过用户就给模型一句说明,让它知道这一步为什么慢了。 */
    private fun waitedHint(waited: Long): String? =
        if (waited >= UserPresence.POLL_MS) "Waited ${waited}ms for you to stop touching the screen before acting." else null

    override suspend fun scroll(ref: String?, snapshotId: String?, down: Boolean): ActionResult {
        val node = when {
            ref != null && snapshotId != null -> entryOf(ref, snapshotId)?.node
            else -> null
        }?.let { n -> runCatching { n }.getOrNull() }
        if (node != null) {
            waitForUser()
            val action = if (down) AccessibilityNodeInfo.ACTION_SCROLL_FORWARD else AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
            val ok = runCatching { node.performAction(action) }.getOrDefault(false)
            if (ok) return ActionResult.Ok(changed = null)
        }
        // 节点滚不动就用手势:屏中部竖着划一段
        val from = if (down) height * 3 / 4 else height / 4
        val to = if (down) height / 4 else height * 3 / 4
        return swipe(width / 2, from, width / 2, to, 400L)
    }

    override suspend fun swipe(x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Long): ActionResult {
        val waited = waitForUser()
        markSelf(durationMs + 500L)
        val path = Path().apply {
            moveTo(x1.toFloat(), y1.toFloat())
            lineTo(x2.toFloat(), y2.toFloat())
        }
        val ok = runCatching { a11y.gesture(Display.DEFAULT_DISPLAY, path, durationMs.coerceAtLeast(1L)) }
            .getOrDefault(false)
        return if (ok) ActionResult.Ok(changed = null, hint = waitedHint(waited)) else ActionResult.Failed(SWIPE_FAILED, HINT)
    }

    override suspend fun typeText(ref: String?, snapshotId: String?, text: String): ActionResult {
        val node = when {
            ref != null && snapshotId != null -> entryOf(ref, snapshotId)?.node
            else -> withContext(Dispatchers.IO) { runCatching { a11y.rootInActiveWindow?.findFocus(AccessibilityNodeInfo.FOCUS_INPUT) }.getOrNull() }
        } ?: return ActionResult.Failed(NO_FOCUSED_FIELD, HINT_TYPE)
        runCatching { node.performAction(AccessibilityNodeInfo.ACTION_FOCUS) }
        val args = Bundle().apply { putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text) }
        val ok = runCatching { node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args) }.getOrDefault(false)
        return if (ok) ActionResult.Ok(changed = null) else ActionResult.Failed(TYPE_FAILED, HINT_TYPE)
    }

    override suspend fun clearText(ref: String?, snapshotId: String?): ActionResult = typeText(ref, snapshotId, "")

    override suspend fun pressKey(keyCode: Int): ActionResult = when (keyCode) {
        android.view.KeyEvent.KEYCODE_BACK -> back()
        else -> ActionResult.Failed(KEY_UNSUPPORTED, HINT)
    }

    override suspend fun back(): ActionResult {
        val ok = runCatching { a11y.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK) }.getOrDefault(false)
        return if (ok) ActionResult.Ok(changed = null) else ActionResult.Failed(BACK_FAILED, HINT)
    }

    override suspend fun openApp(packageName: String, cold: Boolean): ActionResult = withContext(Dispatchers.IO) {
        val intent = runCatching { a11y.packageManager.getLaunchIntentForPackage(packageName) }.getOrNull()
            ?: return@withContext ActionResult.Failed(APP_NOT_FOUND, HINT_APP)
        intent.addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
        val ok = runCatching { a11y.startActivity(intent) }.isSuccess
        if (!ok) return@withContext ActionResult.Failed(APP_NOT_FOUND, HINT_APP)
        // 开在用户主屏上;降级模式没有虚拟屏可"挪",交付结果如实说开在哪儿
        ActionResult.Ok(changed = true, hint = HINT_OPENED_ON_USER_SCREEN)
    }

    /**
     * 主屏截图里带着钉住的状态栏和底部导航栏。长截图要把它们裁掉,否则每帧的导航栏都会拼进图中间。
     * 返回新位图,原图由调用方回收。
     */
    private fun cropChrome(frame: Bitmap): Bitmap {
        val top = (frame.height * 0.055).toInt()
        val bottom = (frame.height * 0.060).toInt()
        val h = frame.height - top - bottom
        if (h < 100) return frame
        return runCatching { Bitmap.createBitmap(frame, 0, top, frame.width, h) }.getOrDefault(frame)
    }

    /** 主屏截图:拿一张位图(调用方负责回收)。系统限制两次截图间隔,拿不到返回 null。 */
    private suspend fun shotBitmap(): Bitmap? = withContext(Dispatchers.IO) {
        val shot = runCatching { a11y.takeMainScreenshot() }.getOrNull()
        (shot as? ScreenAccessibility.MainShot.Ok)?.bitmap
    }

    /**
     * 降级模式的长截图:主屏截图 + 手势滚动 + 按内容锚点拼接(逻辑在 [LongShotStitcher]/[LongShotMath])。
     * 主屏截图有最小间隔,所以每滚一屏多等一会儿;横向长截图先转 90° 拼再转回来。
     */
    override suspend fun longShot(maxScreens: Int, horizontal: Boolean): com.wangzan101.mika.core.uistate.LongShot? =
        withContext(Dispatchers.IO) {
            val limit = maxScreens.coerceIn(1, 12)
            val frames = mutableListOf<Bitmap>()
            val shifts = mutableListOf<Int>()
            var blocked: String? = null
            try {
                val firstRaw = shotBitmap() ?: return@withContext null
                val first = cropChrome(firstRaw)
                if (first !== firstRaw) firstRaw.recycle()
                frames += if (horizontal) LongShotStitcher.rotate(first, true).also { first.recycle() } else first
                while (frames.size < limit) {
                    val last = frames.last()
                    val h = last.height
                    val w = last.width
                    val r = if (horizontal) {
                        swipe((w * 0.80).toInt(), h / 2, (w * 0.20).toInt(), h / 2, 700L)
                    } else {
                        // 主屏手势比虚拟屏"钝",位移要给足才真的滚起来
                        swipe(w / 2, (h * 0.80).toInt(), w / 2, (h * 0.40).toInt(), 800L)
                    }
                    if (r is ActionResult.Failed) { blocked = "滚动没有成功"; break }
                    delay(1_100) // 主屏截图至少隔一秒
                    val minOverlap = (h * 0.10).toInt()
                    var d = 0
                    var work: Bitmap? = null
                    // 先试手势滑动;主屏上有时手势滚不动(页面把触摸交给别处),再退回无障碍滚动动作
                    repeat(2) { attempt ->
                        val raw = shotBitmap() ?: return@repeat
                        val next = cropChrome(raw)
                        if (next !== raw) raw.recycle()
                        val candidate = if (horizontal) LongShotStitcher.rotate(next, true).also { next.recycle() } else next
                        val shift = LongShotStitcher.shift(last, candidate, minOverlap)
                        Log.i("MainScreenPort", "long shot attempt=$attempt shift=$shift of $h")
                        if (shift >= 32) { d = shift; work = candidate; return@repeat }
                        candidate.recycle()
                        if (attempt == 0) {
                            // 手势没滚起来:用无障碍的滚动动作再试一次
                            scroll(null, null, down = true)
                            delay(900)
                        }
                    }
                    val nextFrame = work ?: break
                    Log.i("MainScreenPort", "long shot shift=$d of $h")
                    if (d > h - minOverlap) { blocked = "页面跳得太远、和上一屏接不上"; nextFrame.recycle(); break }
                    frames += nextFrame
                    shifts += d
                }
                val stitched = LongShotStitcher.stitch(frames, shifts, blocked) ?: return@withContext null
                val segments = if (horizontal) unrotate(stitched.segments) else stitched.segments
                val outWidth = if (horizontal) stitched.height else stitched.width
                val outHeight = if (horizontal) stitched.width else stitched.height
                com.wangzan101.mika.core.uistate.LongShot(
                    segments, outWidth, outHeight, stitched.screens, stitched.overlaps, stitched.blocked,
                )
            } catch (e: CancellationException) {
                throw e
            } catch (e: Throwable) {
                Log.w("MainScreenPort", "long shot failed", e)
                null
            } finally {
                frames.forEach { it.recycle() }
            }
        }

    private fun unrotate(segments: List<ByteArray>): List<ByteArray> = segments.mapNotNull { bytes ->
        val bmp = android.graphics.BitmapFactory.decodeByteArray(bytes, 0, bytes.size) ?: return@mapNotNull null
        val rotated = LongShotStitcher.rotate(bmp, false)
        bmp.recycle()
        ByteArrayOutputStream().use { out ->
            rotated.compress(Bitmap.CompressFormat.PNG, 100, out)
            rotated.recycle()
            out.toByteArray()
        }
    }

    override suspend fun systemAction(action: SystemAction): SystemActionResult = SystemActionResult(
        ActionResult.Failed(SYSTEM_UNSUPPORTED, HINT),
    )

    override suspend fun waitStable(timeoutMs: Long): Boolean {
        delay(300)
        return true
    }

    companion object {
        const val NOT_TAPPABLE = "not_tappable"
        const val TAP_FAILED = "tap_failed"
        const val SWIPE_FAILED = "swipe_failed"
        const val NO_FOCUSED_FIELD = "no_focused_field"
        const val TYPE_FAILED = "type_failed"
        const val KEY_UNSUPPORTED = "key_unsupported"
        const val BACK_FAILED = "back_failed"
        const val APP_NOT_FOUND = "app_not_found"
        const val SYSTEM_UNSUPPORTED = "system_action_unsupported"

        const val HINT =
            "This action is not available in the fallback mode: the built-in helper is not connected, so Mika works on " +
                "your main screen with accessibility only. Reconnect the helper from Settings › Phone for the full set."
        const val HINT_TAP = "That element has no tappable area in fallback mode. Read the screen again, or use coordinates."
        const val HINT_TYPE = "No text field has focus. Tap the field first, then type."
        const val HINT_APP = "That app has no launchable screen on this phone."
        /** 这个进程里已经提示过「正在读主屏」了。 */
        private val NOTICE_SHOWN = java.util.concurrent.atomic.AtomicBoolean(false)

        const val HINT_OPENED_ON_USER_SCREEN =
            "Opened on your main screen (fallback mode: the built-in helper is not connected)."
    }
}
