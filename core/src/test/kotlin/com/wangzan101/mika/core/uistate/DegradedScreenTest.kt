package com.wangzan101.mika.core.uistate

import com.wangzan101.mika.core.assembly.toolDispatcher
import com.wangzan101.mika.core.model.Part
import com.wangzan101.mika.core.prompt.Feedback
import com.wangzan101.mika.core.tool.FakeScreen
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 降级模式(读用户自己的主屏)必须在读屏结果里说明白:
 * 不然模型会按"后台虚拟屏可以随便折腾"的假设操作,把用户眼前的屏幕来回滚。
 */
class DegradedScreenTest {
    /** 虚拟屏:默认形态。 */
    private class VirtualScreen : ScreenPort by FakeScreen() {
        override suspend fun snapshot() = ScreenSnapshot("p1", "com.example", emptyList(), 1080, 2400)
    }

    /** 降级模式:走用户自己的主屏。 */
    private class MainScreen : ScreenPort by FakeScreen() {
        override val degradedScreen: Boolean get() = true
        override suspend fun snapshot() = ScreenSnapshot("p1", "com.example", emptyList(), 1080, 2400)
    }

    private fun JsonObject.s(k: String) = this[k]?.jsonPrimitive?.content

    private suspend fun observe(screen: ScreenPort) = toolDispatcher(screen, vision = null)
        .executeRead(Part.ToolCall("o", "phone_observe", "{}")).content

    @Test fun degradedObservationSaysSoAndExplainsTheCost() = runTest {
        val r = observe(MainScreen())
        assertEquals("true", r.s("degraded"))
        val note = r.s("note").orEmpty()
        assertTrue("note 要说明在用户自己的屏幕上: $note", note.contains(Feedback["degraded_screen"]))
    }

    @Test fun normalObservationHasNoDegradedFlag() = runTest {
        val r = observe(VirtualScreen())
        assertEquals(null, r.s("degraded"))
        assertTrue(r.s("note").orEmpty().contains(Feedback["degraded_screen"]).not())
    }

    @Test fun degradedNoteIsAddedNextToTheChangingNote() = runTest {
        // 屏在变 + 降级:两条 note 都要在,不能互相盖掉
        val both = object : ScreenPort by FakeScreen() {
            override val degradedScreen: Boolean get() = true
            override suspend fun snapshot() = ScreenSnapshot("p1", "com.example", emptyList(), 1080, 2400, changedDuringRead = true)
        }
        val r = observe(both)
        val note = r.s("note").orEmpty()
        assertTrue(note.contains(Feedback["changed_during_read"]))
        assertTrue(note.contains(Feedback["degraded_screen"]))
    }
}
