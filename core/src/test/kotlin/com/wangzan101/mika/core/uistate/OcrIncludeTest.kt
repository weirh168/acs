package com.wangzan101.mika.core.uistate

import com.wangzan101.mika.core.assembly.toolDispatcher
import com.wangzan101.mika.core.model.Part
import com.wangzan101.mika.core.tool.FakeScreen
import com.wangzan101.mika.core.vision.JvmTestImageOps
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** includeOcr:树够用时也能强制读一次字,并把「只在像素上有」的行单独返回。 */
class OcrIncludeTest {

    private fun el(i: Int, name: String, bounds: List<Int>, clickable: Boolean = false) =
        UiElement("@e$i", "TextView", name, 0, 0, bounds, null, clickable, false, false)

    /** 竖排一列有名字的可点元素:树明显够用(>= 6 个有名字的)。 */
    private fun rows(n: Int, top: Int = 100) = (0 until n).map { i ->
        el(i + 1, "第${i + 1}行", listOf(50, top + i * 60, 950, top + i * 60 + 50), clickable = true)
    }

    private class OcrScreen(val elements: List<UiElement>, val lines: List<VisibleTextLine>) : ScreenPort by FakeScreen() {
        var ocrReads = 0
        override suspend fun snapshot() = ScreenSnapshot("p1", "com.example", elements, 1080, 2400)
        override suspend fun peek() = snapshot()
        override suspend fun readVisibleText(): List<VisibleTextLine> { ocrReads++; return lines }
        override suspend fun screenshotPng(): ByteArray = JvmTestImageOps.encode(108, 240) { _, _ -> 128 }
    }

    private fun JsonObject.s(k: String) = this[k]?.jsonPrimitive?.content

    /** 一屏 8 行字;OCR 认出两行:一行和树里第 8 行重合(应被滤掉),一行只在像素上。 */
    private fun screen(): OcrScreen {
        val elements = rows(8)
        val eighth = elements[7].bounds
        return OcrScreen(elements, listOf(
            VisibleTextLine("第8行", eighth),
            VisibleTextLine("7:42", listOf(800, 2000, 900, 2040)),
        ))
    }

    @Test fun adequateTreeSkipsOcrUnlessAsked() = runTest {
        val s = screen()
        val r = toolDispatcher(s).executeRead(Part.ToolCall("o", "phone_observe", "{}"))
        assertEquals(0, s.ocrReads)
        assertNull(r.content["ocrOnly"])
        assertNull(r.content["ocrMs"])
    }

    @Test fun includeOcrReadsPixelsAndReturnsPixelOnlyLines() = runTest {
        val s = screen()
        val r = toolDispatcher(s).executeRead(Part.ToolCall("o", "phone_observe", """{"includeOcr":true}"""))
        assertEquals(1, s.ocrReads)
        // 树够用:visibleText 给全部认出的行
        val all = r.content["visibleText"]!!.jsonArray.map { it.jsonObject }
        assertEquals(listOf("7:42", "第8行"), all.mapNotNull { it.s("text") }.sorted())
        // ocrOnly 只留树里没有的那一行,并带 0–999 的中心点
        val only = r.content["ocrOnly"]!!.jsonArray.map { it.jsonObject }
        assertEquals(listOf("7:42"), only.map { it.s("text") })
        assertEquals(listOf(850, 2020), only.first()["center"]!!.jsonArray.map { it.jsonPrimitive.content.toInt() })
        assertTrue(r.content["ocrMs"]!!.jsonPrimitive.content.toLong() >= 0L)
    }

    @Test fun ocrStillRunsWhenTreeNeedsItEvenWithoutTheFlag() = runTest {
        val s = OcrScreen(emptyList(), listOf(VisibleTextLine("画布上的字", listOf(100, 100, 600, 140))))
        val r = toolDispatcher(s).executeRead(Part.ToolCall("o", "phone_observe", "{}"))
        assertEquals(1, s.ocrReads)
        assertEquals("unusable", r.content.s("treeQuality"))
        assertEquals("画布上的字", r.content["visibleText"]!!.jsonArray.single().jsonObject.s("text"))
        assertEquals("画布上的字", r.content["ocrOnly"]!!.jsonArray.single().jsonObject.s("text"))
    }
}
