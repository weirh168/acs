package com.wangzan101.mika.core.cap.phone

import com.wangzan101.mika.core.assembly.toolDispatcher
import com.wangzan101.mika.core.model.Part
import com.wangzan101.mika.core.tool.FakeScreen
import com.wangzan101.mika.core.tool.execute
import com.wangzan101.mika.core.uistate.ScreenPort
import com.wangzan101.mika.core.uistate.ScreenSnapshot
import com.wangzan101.mika.core.uistate.UiElement
import com.wangzan101.mika.core.uistate.VisibleTextLine
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.After

/** 三个手机复合工具:tap_ocr、read_chat、long_screenshot。 */
class CompositeToolsTest {

    private fun JsonObject.s(k: String) = this[k]?.jsonPrimitive?.content

    @After fun resetDebugFlag() { com.wangzan101.mika.core.cap.phone.PhoneDebug.allowForceWait = false }

    private class Phone(
        private val lines: List<List<VisibleTextLine>>,
        private val shot: com.wangzan101.mika.core.uistate.LongShot? = null,
        private val vision: Boolean = false,
    ) : ScreenPort by FakeScreen() {
        var reads = 0
        var scrolls = 0
        val downFlags = mutableListOf<Boolean>()
        var scrollStopAfter: Int? = null
        var taps = mutableListOf<Pair<Int, Int>>()
        var lastRegion: List<Int>? = null
        override suspend fun snapshot() = ScreenSnapshot("p1", "com.example",
            listOf(UiElement("@e1", "TextView", "标题", 0, 0, listOf(0, 0, 999, 100), null, false, false, false)), 1080, 2400)
        override suspend fun peek() = snapshot()
        override suspend fun readVisibleText(): List<VisibleTextLine> {
            val i = reads.coerceAtMost(lines.lastIndex)
            reads++
            return lines[i]
        }
        override suspend fun readVisibleTextIn(region: List<Int>?): List<VisibleTextLine>? {
            lastRegion = region
            return readVisibleText()
        }
        override suspend fun scroll(ref: String?, snapshotId: String?, down: Boolean): com.wangzan101.mika.core.uistate.ActionResult {
            scrolls++
            downFlags += down
            if (scrollStopAfter != null && scrolls >= scrollStopAfter!!) {
                return com.wangzan101.mika.core.uistate.ActionResult.Ok(changed = false)
            }
            return com.wangzan101.mika.core.uistate.ActionResult.Ok(changed = true)
        }
        override suspend fun tapXY(x: Int, y: Int) = run {
            taps += x to y
            com.wangzan101.mika.core.uistate.ActionResult.Ok(changed = true)
        }
        override suspend fun longShot(maxScreens: Int, horizontal: Boolean) = shot
    }

    // ── 长截图：startFrom / settleMs ─────────────────────────────────────────

    private fun shotFor() = com.wangzan101.mika.core.uistate.LongShot(listOf(byteArrayOf(1)), 1080, 9000, 3)

    @Test fun longShotStartFromTopScrollsUpUntilTheEdge() = runTest {
        val p = Phone(listOf(emptyList()), shot = shotFor())
        p.scrollStopAfter = 3
        val t = toolDispatcher(p, visionEnabled = true)
        t.execute(Part.ToolCall("o", "phone_observe", "{}"))
        val r = t.execute(Part.ToolCall("c1", "phone_long_screenshot", """{"startFrom":"top","maxScreens":3}""")).content
        assertEquals("true", r.s("ok"))
        assertEquals("top", r.s("startFrom"))
        assertEquals("3", r.s("preScrolls"))
        assertEquals("true", r.s("atEdge"))
        assertEquals(listOf(false, false, false), p.downFlags)   // 往上滚
    }

    @Test fun longShotStartFromBottomScrollsDown() = runTest {
        val p = Phone(listOf(emptyList()), shot = shotFor())
        p.scrollStopAfter = 2
        val t = toolDispatcher(p, visionEnabled = true)
        t.execute(Part.ToolCall("o", "phone_observe", "{}"))
        val r = t.execute(Part.ToolCall("c1", "phone_long_screenshot", """{"startFrom":"bottom"}""")).content
        assertEquals("bottom", r.s("startFrom"))
        assertEquals("2", r.s("preScrolls"))
        assertEquals(listOf(true, true), p.downFlags)
    }

    @Test fun longShotCurrentDoesNotScrollFirst() = runTest {
        val p = Phone(listOf(emptyList()), shot = shotFor())
        val t = toolDispatcher(p, visionEnabled = true)
        t.execute(Part.ToolCall("o", "phone_observe", "{}"))
        val r = t.execute(Part.ToolCall("c1", "phone_long_screenshot", """{"maxScreens":2}""")).content
        assertEquals("current", r.s("startFrom"))
        assertEquals("0", p.scrolls.toString())
        assertEquals(null, r.s("preScrolls"))
    }

    @Test fun longShotRejectsUnknownStartFrom() = runTest {
        val p = Phone(listOf(emptyList()), shot = shotFor())
        val t = toolDispatcher(p, visionEnabled = true)
        t.execute(Part.ToolCall("o", "phone_observe", "{}"))
        val r = t.execute(Part.ToolCall("c1", "phone_long_screenshot", """{"startFrom":"middle"}""")).content
        assertEquals("invalid_start_from", r.s("error"))
    }

    // ── match：只取含关键词的行 ─────────────────────────────────────────────

    private fun chatScreen() = listOf(
        VisibleTextLine("张三：明天开会", listOf(0, 0, 100, 40)),
        VisibleTextLine("李四：收到", listOf(0, 50, 100, 90)),
        VisibleTextLine("张三：发票我发邮箱了", listOf(0, 100, 100, 140)),
    )

    @Test fun readChatMatchKeepsOnlyLinesContainingIt() = runTest {
        val p = Phone(listOf(chatScreen()))
        val r = d(p).execute(Part.ToolCall("c1", "phone_read_chat", """{"match":"张三","maxScreens":1}""")).content
        val lines = r["lines"]!!.jsonArray.map { (it as JsonPrimitive).content }
        assertEquals(listOf("张三：明天开会", "张三：发票我发邮箱了"), lines)
        assertEquals("2", r.s("matched"))
        assertEquals("1", r.s("dropped"))
    }

    @Test fun readChatMatchIsCaseInsensitive() = runTest {
        val p = Phone(listOf(listOf(
            VisibleTextLine("WLAN 已连接", listOf(0, 0, 100, 40)),
            VisibleTextLine("蓝牙 已关闭", listOf(0, 50, 100, 90)),
        )))
        val r = d(p).execute(Part.ToolCall("c1", "phone_read_chat", """{"match":"wlan","maxScreens":1}""")).content
        val lines = r["lines"]!!.jsonArray.map { (it as JsonPrimitive).content }
        assertEquals(listOf("WLAN 已连接"), lines)
    }

    @Test fun readChatMatchWithNoHitExplainsItself() = runTest {
        val p = Phone(listOf(chatScreen()))
        val r = d(p).execute(Part.ToolCall("c1", "phone_read_chat", """{"match":"王五","maxScreens":1}""")).content
        assertEquals("0", r.s("matched"))
        assertEquals("3", r.s("dropped"))
        assertTrue(r.s("hint")!!.contains("王五"))
    }

    /** 手机一组是收着的:先读一屏把它展开,后面才能按名字调组里的工具。 */
    private suspend fun d(port: ScreenPort) = toolDispatcher(port).also {
        it.execute(Part.ToolCall("open", "phone_observe", "{}"))
    }

    @Test fun tapOcrTapsTheMatchedLineCenter() = runTest {
        val p = Phone(listOf(listOf(
            VisibleTextLine("跳过", listOf(800, 80, 950, 130)),
            VisibleTextLine("开始游戏", listOf(300, 1800, 800, 1900)),
        )))
        val r = d(p).execute(Part.ToolCall("c1", "phone_tap_ocr", """{"text":"开始游戏"}""")).content
        assertEquals(r.toString(), "开始游戏", r.s("matchedText"))
        assertEquals("550", r.s("x"))
        assertEquals("1850", r.s("y"))
        assertEquals(1, p.taps.size)
        // 0–999 坐标换成像素:550/999*(1080-1)≈593,1850/999*(2400-1)≈4444
        assertEquals(594 to 4443, p.taps.single())
        assertTrue(r.s("ok") == "true")
    }

    @Test fun tapOcrPrefersShortestContainingLineAndCanBeExact() = runTest {
        val p = Phone(listOf(listOf(
            VisibleTextLine("立即购买并付款", listOf(100, 100, 900, 160)),
            VisibleTextLine("立即购买", listOf(200, 200, 800, 260)),
        )))
        val loose = d(p).execute(Part.ToolCall("c1", "phone_tap_ocr", """{"text":"立即购买"}""")).content
        assertEquals("立即购买", loose.s("matchedText"))
        assertEquals("1", loose.s("alsoMatched"))
    }

    @Test fun tapOcrNoMatchListsNearbyLines() = runTest {
        val p = Phone(listOf(listOf(VisibleTextLine("开始游戏", listOf(0, 0, 100, 100)))))
        val r = d(p).execute(Part.ToolCall("c1", "phone_tap_ocr", """{"text":"开始对局"}""")).content
        assertEquals("ocr_no_match", r.s("error"))
        assertTrue(r.s("message")!!.contains("开始游戏"))
        assertEquals(0, p.taps.size)
    }

    @Test fun readChatMergesScreensAndStopsWhenNothingNew() = runTest {
        val p = Phone(listOf(
            emptyList(),
            listOf(VisibleTextLine("第一条", listOf(0, 0, 100, 50)), VisibleTextLine("第二条", listOf(0, 60, 100, 100))),
            listOf(VisibleTextLine("第二条", listOf(0, 0, 100, 50)), VisibleTextLine("第三条", listOf(0, 60, 100, 100))),
            listOf(VisibleTextLine("第三条", listOf(0, 0, 100, 50))),
        ))
        val r = d(p).execute(Part.ToolCall("c1", "phone_read_chat", """{"maxScreens":5}""")).content
        val lines = r["lines"]!!.jsonArray.map { (it as JsonPrimitive).content }
        assertEquals(listOf("第一条", "第二条", "第三条"), lines)
        assertEquals("3", r.s("screens"))
        assertEquals("2", p.scrolls.toString())
    }

    @Test fun longScreenshotReturnsSizeAndScreens() = runTest {
        val shot = com.wangzan101.mika.core.uistate.LongShot(listOf(byteArrayOf(1, 2, 3)), 1080, 6000, 4)
        val p = Phone(listOf(emptyList()), shot = shot)
        val t = toolDispatcher(p, visionEnabled = true)
        t.execute(Part.ToolCall("o", "phone_observe", "{}"))
        val r = t.execute(Part.ToolCall("c1", "phone_long_screenshot", """{"maxScreens":6}""")).content
        assertEquals(r.toString(), "6000", r.s("height"))
        assertEquals("4", r.s("screens"))
    }

    @Test fun longScreenshotRejectsUnknownDirection() = runTest {
        val p = Phone(listOf(emptyList()), shot = null)
        val r = d(p).execute(Part.ToolCall("c1", "phone_long_screenshot", """{"direction":"diagonal","savePath":"/workspace/a.png"}""")).content
        assertEquals("invalid_direction", r.s("error"))
    }

    @Test fun blockedShotCarriesHint() = runTest {
        val shot = com.wangzan101.mika.core.uistate.LongShot(
            listOf(byteArrayOf(1)), 1080, 4800, 2, listOf(330), "画面被弹窗或遮罩盖住了",
        )
        val p = Phone(listOf(emptyList()), shot = shot)
        val t = toolDispatcher(p, visionEnabled = true)
        t.execute(Part.ToolCall("o", "phone_observe", "{}"))
        val r = t.execute(Part.ToolCall("c1", "phone_long_screenshot", "{}")).content
        assertEquals("画面被弹窗或遮罩盖住了", r.s("blocked"))
        assertTrue(r.s("hint")!!.contains("弹窗"))
    }

    @Test fun segmentedShotNeedsSavePath() = runTest {
        val shot = com.wangzan101.mika.core.uistate.LongShot(
            listOf(byteArrayOf(1), byteArrayOf(2)), 1080, 12000, 6,
        )
        val p = Phone(listOf(emptyList()), shot = shot)
        val t = toolDispatcher(p, visionEnabled = true)
        t.execute(Part.ToolCall("o", "phone_observe", "{}"))
        val r = t.execute(Part.ToolCall("c1", "phone_long_screenshot", "{}")).content
        assertEquals("save_path_required", r.s("error"))
        assertTrue(r.s("message")!!.contains("split"))
    }

    @Test fun tapOcrPassesRegionToThePort() = runTest {
        val p = Phone(listOf(listOf(VisibleTextLine("立即购买", listOf(200, 200, 800, 260)))))
        val r = d(p).execute(Part.ToolCall("c1", "phone_tap_ocr", """{"text":"立即购买","region":"0,0,999,400"}""")).content
        assertEquals("true", r.s("ok"))
        assertEquals(listOf(0, 0, 999, 400), p.lastRegion)
    }

    @Test fun tapOcrRejectsBadRegion() = runTest {
        val p = Phone(listOf(listOf(VisibleTextLine("x", listOf(0, 0, 10, 10)))))
        val r = d(p).execute(Part.ToolCall("c1", "phone_tap_ocr", """{"text":"x","region":"400,0,100,999"}""")).content
        assertEquals("invalid_region", r.s("error"))
        assertEquals(0, p.taps.size)
    }

    @Test fun readChatUsesRegion() = runTest {
        val p = Phone(listOf(emptyList(), listOf(VisibleTextLine("第一条", listOf(0, 0, 100, 50)))))
        val r = d(p).execute(Part.ToolCall("c1", "phone_read_chat", """{"maxScreens":1,"region":"0,500,999,999"}""")).content
        assertEquals(listOf(0, 500, 999, 999), p.lastRegion)
        assertEquals("true", r.s("ok"))
    }

    @Test fun toolsAreOfferedAndUnavailableLongShotFails() = runTest {
        val p = Phone(listOf(emptyList()), shot = null)
        val names = d(p).definitions().map { it.name }
        assertTrue("phone_tap_ocr" in names)
        assertTrue("phone_read_chat" in names)
        assertTrue("phone_long_screenshot" in names)
        val r = d(p).execute(Part.ToolCall("c1", "phone_long_screenshot", "{}")).content
        assertEquals("save_path_required", r.s("error"))
    }

    // ── direction=up：往上读旧内容，返回行仍是阅读顺序 ────────────────────────────

    @Test fun readChatUpwardsStitchesOlderScreensFirst() = runTest {
        // observe 吃掉第 0 屏；之后第 1 屏是「较新的」，第 2 屏是往上滚出来的「更旧的」
        val p = Phone(listOf(
            emptyList(),
            listOf(VisibleTextLine("消息3", listOf(0, 0, 100, 50)), VisibleTextLine("消息4", listOf(0, 60, 100, 100))),
            listOf(VisibleTextLine("消息1", listOf(0, 0, 100, 50)), VisibleTextLine("消息2", listOf(0, 60, 100, 100))),
        ))
        val r = d(p).execute(Part.ToolCall("c1", "phone_read_chat", """{"maxScreens":2,"direction":"up"}""")).content
        val lines = r["lines"]!!.jsonArray.map { (it as JsonPrimitive).content }
        assertEquals(listOf("消息1", "消息2", "消息3", "消息4"), lines)
        assertEquals("up", r.s("direction"))
        assertEquals(listOf(false), p.downFlags)
    }

    @Test fun readChatDownwardsKeepsScreenOrder() = runTest {
        val p = Phone(listOf(
            emptyList(),
            listOf(VisibleTextLine("消息1", listOf(0, 0, 100, 50))),
            listOf(VisibleTextLine("消息2", listOf(0, 0, 100, 50))),
        ))
        val r = d(p).execute(Part.ToolCall("c1", "phone_read_chat", """{"maxScreens":2}""")).content
        val lines = r["lines"]!!.jsonArray.map { (it as JsonPrimitive).content }
        assertEquals(listOf("消息1", "消息2"), lines)
        assertEquals("down", r.s("direction"))
        assertEquals(listOf(true), p.downFlags)
    }

    @Test fun readChatRejectsUnknownDirection() = runTest {
        val p = Phone(listOf(emptyList()))
        val r = d(p).execute(Part.ToolCall("c1", "phone_read_chat", """{"direction":"sideways-left"}""")).content
        assertEquals("invalid_direction", r.s("error"))
    }

    @Test fun readChatAcceptsSettleMs() = runTest {
        val p = Phone(listOf(
            emptyList(),
            listOf(VisibleTextLine("第一条", listOf(0, 0, 100, 50))),
        ))
        val r = d(p).execute(Part.ToolCall("c1", "phone_read_chat", """{"settleMs":120}""")).content
        assertEquals("true", r.s("ok"))
    }

    // ── index：同名文字出现多次时点第 N 个 ──────────────────────────────────────

    private fun threeSends() = listOf(
        VisibleTextLine("发送", listOf(100, 300, 900, 360)),
        VisibleTextLine("发送", listOf(100, 600, 900, 660)),
        VisibleTextLine("发送", listOf(100, 900, 900, 960)),
    )

    @Test fun tapOcrIndexPicksTheNthMatch() = runTest {
        val p = Phone(listOf(threeSends()))
        val r = d(p).execute(Part.ToolCall("c1", "phone_tap_ocr", """{"text":"发送","index":1}""")).content
        assertEquals("true", r.s("ok"))
        assertEquals("1", r.s("index"))
        assertEquals("3", r.s("total"))
        assertEquals("2", r.s("alsoMatched"))
        // 第二个的中心 y=630 → roundToInt(630*2399/999)=1513
        assertEquals(1, p.taps.size)
        assertEquals(1513, p.taps.single().second)
    }

    @Test fun tapOcrIndexOutOfRangeFailsWithoutTapping() = runTest {
        val p = Phone(listOf(threeSends()))
        val r = d(p).execute(Part.ToolCall("c1", "phone_tap_ocr", """{"text":"发送","index":9}""")).content
        assertEquals("ocr_index_out_of_range", r.s("error"))
        assertEquals(0, p.taps.size)
    }

    @Test fun tapOcrDefaultIndexIsZero() = runTest {
        val p = Phone(listOf(threeSends()))
        val r = d(p).execute(Part.ToolCall("c1", "phone_tap_ocr", """{"text":"发送"}""")).content
        assertEquals("0", r.s("index"))
        assertEquals("3", r.s("total"))
        // 第一个的中心 y=330 → 330/999*2399≈792
        assertEquals(792, p.taps.single().second)
    }

    // ── until：读到标志行就停，并把它一起收下 ─────────────────────────────────

    @Test fun readChatStopsAtUntilLineInclusive() = runTest {
        val p = Phone(listOf(listOf(
            VisibleTextLine("消息A", listOf(0, 0, 100, 40)),
            VisibleTextLine("消息B", listOf(0, 50, 100, 90)),
            VisibleTextLine("2026年11月1日", listOf(0, 100, 100, 140)),
            VisibleTextLine("消息C", listOf(0, 150, 100, 190)),
        )))
        val r = d(p).execute(Part.ToolCall("c1", "phone_read_chat", """{"until":"11月1日","maxScreens":5}""")).content
        val lines = r["lines"]!!.jsonArray.map { (it as JsonPrimitive).content }
        assertEquals(listOf("消息A", "消息B", "2026年11月1日"), lines)
        assertEquals("until", r.s("stoppedBy"))
        assertEquals("0", p.scrolls.toString())
    }

    @Test fun readChatWithoutUntilReadsWholeScreen() = runTest {
        val p = Phone(listOf(listOf(
            VisibleTextLine("消息A", listOf(0, 0, 100, 40)),
            VisibleTextLine("消息B", listOf(0, 50, 100, 90)),
        )))
        val r = d(p).execute(Part.ToolCall("c1", "phone_read_chat", """{"maxScreens":1}""")).content
        val lines = r["lines"]!!.jsonArray.map { (it as JsonPrimitive).content }
        assertEquals(listOf("消息A", "消息B"), lines)
        assertEquals(null, r.s("stoppedBy"))
    }

    // ── waitMs：界面还在动时重读，直到出现命中 ───────────────────────────────

    @Test fun tapOcrWaitsUntilTextAppears() = runTest {
        val p = Phone(listOf(
            emptyList(),                                                   // observe 用
            emptyList(),                                                   // 第一次读：界面还没出来
            listOf(VisibleTextLine("确定", listOf(400, 1200, 700, 1280))),   // 之后有了
        ))
        val r = d(p).execute(Part.ToolCall("c1", "phone_tap_ocr", """{"text":"确定","waitMs":1000}""")).content
        assertEquals("true", r.s("ok"))
        assertEquals("确定", r.s("matchedText"))
        assertEquals(1, p.taps.size)
    }

    @Test fun tapOcrWithoutWaitFailsImmediately() = runTest {
        val p = Phone(listOf(emptyList(), emptyList()))
        val r = d(p).execute(Part.ToolCall("c1", "phone_tap_ocr", """{"text":"确定"}""")).content
        assertEquals("ocr_no_match", r.s("error"))
        assertEquals(0, p.taps.size)
    }

    // ── 调试探针：_forceWaitMs 仅在 PhoneDebug.allowForceWait 打开时生效 ──────────

    @Test fun forceWaitSkipsFirstReadAndReportsWaitedMs() = runTest {
        com.wangzan101.mika.core.cap.phone.PhoneDebug.allowForceWait = true
        val p = Phone(listOf(listOf(VisibleTextLine("确定", listOf(400, 1200, 700, 1280)))))
        val r = d(p).execute(Part.ToolCall("c1", "phone_tap_ocr", """{"text":"确定","_forceWaitMs":600}""")).content
        assertEquals("true", r.s("ok"))
        // 第一次读被故意忽略，等了一轮 250ms 后才点中
        assertEquals("250", r.s("waitedMs"))
        assertEquals(1, p.taps.size)
    }

    @Test fun forceWaitIsIgnoredWhenProbeDisabled() = runTest {
        com.wangzan101.mika.core.cap.phone.PhoneDebug.allowForceWait = false
        val p = Phone(listOf(listOf(VisibleTextLine("确定", listOf(400, 1200, 700, 1280)))))
        val r = d(p).execute(Part.ToolCall("c1", "phone_tap_ocr", """{"text":"确定","_forceWaitMs":600}""")).content
        assertEquals("true", r.s("ok"))
        // 探针关着：照常首帧命中，不等待
        assertEquals(null, r.s("waitedMs"))
    }
}
