package com.wangzan101.mika.core.uistate

import com.wangzan101.mika.core.model.Part
import com.wangzan101.mika.core.tool.FakeScreen
import com.wangzan101.mika.core.tool.execute
import com.wangzan101.mika.core.assembly.toolDispatcher
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Test

/** 到了前台却读不到窗口时,observe 要给出原因码(protected_frame / no_window_here / empty_tree)。 */
class UnreadableReasonTest {

    private fun port(snapshot: ScreenSnapshot) = object : ScreenPort by FakeScreen() {
        override suspend fun snapshot() = snapshot
        override suspend fun peek() = snapshot
    }

    private fun snap(
        hasWindow: Boolean = true,
        captureError: String? = null,
        elements: List<UiElement> = emptyList(),
    ) = ScreenSnapshot(
        snapshotId = "p1",
        packageName = "com.example.secure",
        elements = elements,
        width = 1080,
        height = 2400,
        hasWindow = hasWindow,
        unreadableApp = "com.example.secure",
        captureError = captureError,
    )

    private suspend fun observe(s: ScreenSnapshot) = toolDispatcher(port(s))
        .execute(Part.ToolCall("c1", "phone_observe", "{}")).content

    @Test fun blackFrameSaysProtected() = runTest {
        val r = observe(snap(captureError = "display_capture_unavailable"))
        assertEquals("display_capture_unavailable", r["captureError"]?.jsonPrimitive?.content)
        assertEquals(UNREADABLE_PROTECTED, r["reason"]?.jsonPrimitive?.content)
    }

    @Test fun missingWindowSaysNoWindowHere() = runTest {
        val r = observe(snap(hasWindow = false))
        assertEquals(UNREADABLE_NO_WINDOW, r["reason"]?.jsonPrimitive?.content)
    }

    @Test fun windowWithoutTextSaysEmptyTree() = runTest {
        val r = observe(snap(hasWindow = true))
        assertEquals(UNREADABLE_EMPTY_TREE, r["reason"]?.jsonPrimitive?.content)
    }

    @Test fun readableWindowHasNoReason() = runTest {
        val s = ScreenSnapshot(
            snapshotId = "p1", packageName = "com.example", width = 1080, height = 2400,
            elements = listOf(UiElement("@e1", "button", "确定", 500, 500, listOf(0, 0, 999, 999), null, true, false, false)),
        )
        val r = observe(s)
        assertEquals(null, r["reason"])
    }
}
