package com.wangzan101.mika.core.cap.web

import com.wangzan101.mika.core.assembly.toolDispatcher
import com.wangzan101.mika.core.model.Part
import com.wangzan101.mika.core.tool.FakeScreen
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** web_read_all:把重复条目读成结构化数组,不给 selector 时自动挑一组。 */
class ReadAllTest {

    private fun JsonObject.s(k: String) = this[k]?.jsonPrimitive?.content

    private fun d(web: FakeWebPort) = toolDispatcher(FakeScreen(), web = web)

    private fun ok(json: String) = EvalJs.Ok(json, truncated = false)

    @Test fun itemsBecomeStructuredArray() = runTest {
        val web = FakeWebPort().apply {
            eval = ok("""{"usedSelector":null,"found":3,"items":[
                {"title":"洗衣液","text":"洗衣液 2kg ¥29.9","link":"https://shop.example.com/p/1"},
                {"title":"洗洁精","text":"洗洁精 500ml ¥12.5","link":"https://shop.example.com/p/2"},
                {"title":"垃圾袋","text":"垃圾袋 100只 ¥8.8","link":"https://shop.example.com/p/3"}]}""")
        }
        val r = d(web).executeRead(Part.ToolCall("c1", "web_read_all", "{}")).content
        assertEquals("3", r.s("count"))
        assertEquals("3", r.s("found"))
        assertEquals("true", r.s("autoDetected"))
        val items = r["items"]!!.jsonArray.map { it.jsonObject }
        assertEquals(listOf("洗衣液", "洗洁精", "垃圾袋"), items.map { it.s("title") })
        assertEquals("https://shop.example.com/p/2", items[1].s("link"))
        assertTrue(r.s("hint")!!.contains("selector"))
    }

    @Test fun explicitSelectorIsReportedAndCappedByMaxItems() = runTest {
        val web = FakeWebPort().apply {
            eval = ok("""{"usedSelector":"li.result","found":40,"items":[
                {"text":"a","link":"https://x/1"},{"text":"b","link":"https://x/2"}]}""")
        }
        val r = d(web).executeRead(Part.ToolCall("c1", "web_read_all", """{"selector":"li.result","maxItems":2}""")).content
        assertEquals("li.result", r.s("selector"))
        assertEquals("40", r.s("found"))
        assertEquals("2", r.s("count"))
        assertEquals("true", r.s("truncated"))
    }

    @Test fun emptyPageReturnsHintNotError() = runTest {
        val web = FakeWebPort().apply { eval = ok("""{"usedSelector":null,"found":0,"items":[]}""") }
        val r = d(web).executeRead(Part.ToolCall("c1", "web_read_all", "{}")).content
        assertEquals("0", r.s("count"))
        assertTrue(r.s("hint")!!.contains("no repeated items"))
    }

    @Test fun scriptFailureSurfacesThePortError() = runTest {
        val web = FakeWebPort().apply { eval = EvalJs.Failed("invalid_selector", "bad selector") }
        val r = d(web).executeRead(Part.ToolCall("c1", "web_read_all", """{"selector":"!!"}""")).content
        assertEquals("invalid_selector", r.s("error"))
    }
}
