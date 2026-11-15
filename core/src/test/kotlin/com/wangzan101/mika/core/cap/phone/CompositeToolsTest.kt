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

/** 三个手机复合工具:tap_ocr、read_chat、long_screenshot。 */
class CompositeToolsTest {

    private fun JsonObject.s(k: String) = this[k]?.jsonPrimitive?.content

    private class Phone(
        private val lines: List<List<VisibleTextLine>>,
        private val shot: com.wangzan101.mika.core.uistate.LongShot? = null,
        private val vision: Boolean = false,
    ) : ScreenPort by FakeScreen() {
        var reads = 0
        var scrolls = 0
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
        override suspend fun scroll(ref: String?, snapshotId: String?, down: Boolean) = run {
            scrolls++
            com.wangzan101.mika.core.uistate.ActionResult.Ok(changed = true)
        }
        override suspend fun tapXY(x: Int, y: Int) = run {
            taps += x to y
            com.wangzan101.mika.core.uistate.ActionResult.Ok(changed = true)
        }
        override suspend fun longShot(maxScreens: Int, horizontal: Boolean) = shot
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
}
