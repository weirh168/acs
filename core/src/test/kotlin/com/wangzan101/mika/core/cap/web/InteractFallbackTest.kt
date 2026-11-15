package com.wangzan101.mika.core.cap.web

import com.wangzan101.mika.core.assembly.toolDispatcher
import com.wangzan101.mika.core.model.Part
import com.wangzan101.mika.core.tool.FakeScreen
import com.wangzan101.mika.core.tool.execute
import com.wangzan101.mika.core.uistate.ActionResult
import com.wangzan101.mika.core.uistate.ScreenPort
import com.wangzan101.mika.core.uistate.VisibleTextLine
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** 没有 DevTools 时,web_interact 能退化的退化、不能退化的说清楚。 */
class InteractFallbackTest {

    private fun JsonObject.s(k: String) = this[k]?.jsonPrimitive?.content

    /** 记下原生按键与点击,供断言。 */
    private class Screen(
        private val lines: List<VisibleTextLine> = emptyList(),
    ) : ScreenPort by FakeScreen() {
        val keys = mutableListOf<Int>()
        val taps = mutableListOf<Pair<Int, Int>>()
        override suspend fun pressKey(keyCode: Int): ActionResult {
            keys += keyCode
            return ActionResult.Ok(changed = true)
        }
        override suspend fun tapXY(x: Int, y: Int): ActionResult {
            taps += x to y
            return ActionResult.Ok(changed = true)
        }
        override suspend fun tapRef(ref: String, snapshotId: String) = ActionResult.Ok(changed = true)
        override suspend fun readVisibleText(): List<VisibleTextLine>? = lines
    }

    private suspend fun run(
        web: FakeWebPort,
        screen: ScreenPort,
        args: String,
    ): JsonObject {
        val t = toolDispatcher(screen, web = web)
        t.execute(Part.ToolCall("nav", "web_navigate", """{"url":"https://example.com/"}"""))
        return t.execute(Part.ToolCall("c1", "web_interact", args)).content
    }

    @Test fun plainKeyFallsBackToNativeKeycode() = runTest {
        val web = FakeWebPort().apply { comboResult = ActionResult.Failed(DEVTOOLS_UNAVAILABLE) }
        val screen = Screen()
        val r = run(web, screen, """{"action":"key","key":"Enter"}""")
        assertEquals(r.toString(), "true", r.s("ok"))
        assertTrue(web.calls.contains("key 66"))
    }

    @Test fun tabAndArrowsAlsoMap() = runTest {
        val web = FakeWebPort().apply { comboResult = ActionResult.Failed(DEVTOOLS_UNAVAILABLE) }
        val screen = Screen()
        run(web, screen, """{"action":"key","key":"Tab"}""")
        run(web, screen, """{"action":"key","key":"ArrowDown"}""")
        assertTrue(web.calls.contains("key 61"))
        assertTrue(web.calls.contains("key 20"))
    }

    @Test fun combinedKeySaysItNeedsDevtools() = runTest {
        val web = FakeWebPort().apply { comboResult = ActionResult.Failed(DEVTOOLS_UNAVAILABLE) }
        val screen = Screen()
        val r = run(web, screen, """{"action":"key","key":"Control+A"}""")
        assertEquals("key_modifiers_need_devtools", r.s("error"))
        assertTrue(web.calls.none { it.startsWith("key ") })
    }

    @Test fun hoverOnTouchIsRefusedClearly() = runTest {
        val web = FakeWebPort().apply { result = ActionResult.Failed(DEVTOOLS_UNAVAILABLE) }
        val screen = Screen()
        val r = run(web, screen, """{"action":"hover","x":500,"y":500}""")
        assertEquals("not_supported_on_touch", r.s("error"))
    }

    @Test fun selectFallsBackToTappingTheOptionText() = runTest {
        val web = FakeWebPort().apply {
            selectResult = ActionResult.Failed(DEVTOOLS_UNAVAILABLE)
            visibleText = listOf(VisibleTextLine("北京", listOf(100, 300, 400, 340)))
        }
        val screen = Screen()
        val r = run(web, screen, """{"action":"select","ref":"@e1","snapshotId":"w1","option":"北京"}""")
        assertEquals(r.toString(), "true", r.s("ok"))
        assertTrue(web.calls.any { it.startsWith("tapRef @e1") })
        assertTrue(web.calls.any { it.startsWith("tapXY") })
    }
}
