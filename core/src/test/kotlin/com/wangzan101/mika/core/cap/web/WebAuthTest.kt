package com.wangzan101.mika.core.cap.web

import com.wangzan101.mika.core.assembly.toolDispatcher
import com.wangzan101.mika.core.model.Part
import com.wangzan101.mika.core.tool.FakeScreen
import com.wangzan101.mika.core.tool.execute
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** web_auth:登录墙判定。 */
class WebAuthTest {

    private fun JsonObject.s(k: String) = this[k]?.jsonPrimitive?.content

    private fun ok(json: String) = EvalJs.Ok(json, truncated = false)

    private val LOGIN_WALL = """{"host":"example.com","path":"/login","signals":["password_field","login_form","url_path"],"needsLogin":true}"""
    private val NORMAL = """{"host":"example.com","path":"/article/1","signals":[],"needsLogin":false}"""

    private suspend fun run(payload: String): JsonObject {
        val web = FakeWebPort().apply { eval = ok(payload) }
        val t = toolDispatcher(FakeScreen(), web = web)
        t.execute(Part.ToolCall("nav", "web_navigate", """{"url":"https://example.com/"}"""))
        return t.execute(Part.ToolCall("c1", "web_auth", "{}")).content
    }

    @Test fun loginWallIsReportedWithSignalsAndNextTool() = runTest {
        val r = run(LOGIN_WALL)
        assertEquals("true", r.s("needsLogin"))
        assertEquals("example.com", r.s("host"))
        assertEquals(listOf("password_field", "login_form", "url_path"),
            r["signals"]!!.jsonArray.map { it.jsonPrimitive.content })
        assertEquals("mika_login_site", r.s("nextTool"))
        assertTrue(r.s("hint")!!.contains("example.com"))
    }

    @Test fun readablePageNeedsNoLogin() = runTest {
        val r = run(NORMAL)
        assertEquals("false", r.s("needsLogin"))
        assertTrue(r["signals"]!!.jsonArray.isEmpty())
        assertEquals(null, r.s("nextTool"))
    }

    @Test fun toolIsOffered() = runTest {
        val web = FakeWebPort()
        val names = toolDispatcher(FakeScreen(), web = web).definitions().map { it.name }
        assertTrue("web_auth" in names)
    }
}
