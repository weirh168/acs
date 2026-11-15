package com.wangzan101.mika.core.usage

import com.wangzan101.mika.core.assembly.toolDispatcher
import com.wangzan101.mika.core.model.Part
import com.wangzan101.mika.core.model.Usage
import com.wangzan101.mika.core.self.SelfPort
import com.wangzan101.mika.core.self.SelfUsage
import com.wangzan101.mika.core.tool.FakeScreen
import com.wangzan101.mika.core.tool.ToolContext
import com.wangzan101.mika.core.tool.execute
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** usage_stats:报本次任务与当天的 token 用量。 */
class UsageStatsTest {

    private fun JsonObject.s(k: String) = this[k]?.jsonPrimitive?.content

    /** 只提供 usageToday 的自身端口。 */
    private class UsagePort(private val today: SelfUsage?) : SelfPort {
        override suspend fun status() = com.wangzan101.mika.core.self.SelfStatus()
        override suspend fun openScreen(screen: com.wangzan101.mika.core.self.SelfScreen, note: String?) =
            com.wangzan101.mika.core.self.SelfResult(ok = false)
        override suspend fun openFile(path: String, name: String?) = com.wangzan101.mika.core.self.SelfResult(ok = false)
        override suspend fun notify(title: String, body: String, screen: com.wangzan101.mika.core.self.SelfScreen?) =
            com.wangzan101.mika.core.self.SelfResult(ok = false)
        override suspend fun copy(text: String) = false
        override suspend fun usageToday(): SelfUsage? = today
    }

    @Test fun reportsRunTokensBudgetAndToday() = runTest {
        val tally = RunUsageTally(tokenBudget = 10_000)
        tally.add(Usage(inputTokens = 1_200, outputTokens = 300, cachedInputTokens = 400), httpAttempts = 2)
        val t = toolDispatcher(FakeScreen(), self = UsagePort(SelfUsage(50_000, 40_000, 10_000, 9_000, 12)))
        val r = withContext(tally) { t.execute(Part.ToolCall("c1", "usage_stats", "{}")).content }
        val run = r["run"]!!.jsonObject
        assertEquals("1500", run.s("tokens"))
        assertEquals("1200", run.s("inputTokens"))
        assertEquals("300", run.s("outputTokens"))
        assertEquals("400", run.s("cachedInputTokens"))
        assertEquals("1", run.s("calls"))
        assertEquals("2", run.s("httpCalls"))
        assertEquals("10000", run.s("budget"))
        assertEquals("8500", run.s("remaining"))
        val today = r["today"]!!.jsonObject
        assertEquals("50000", today.s("tokens"))
        assertEquals("12", today.s("calls"))
    }

    @Test fun withoutTallyOrPortStillAnswers() = runTest {
        val r = toolDispatcher(FakeScreen()).execute(Part.ToolCall("c1", "usage_stats", "{}")).content
        assertEquals("false", r["run"]!!.jsonObject.s("available"))
        assertNull(r["today"])
    }

    @Test fun toolIsOffered() = runTest {
        val names = toolDispatcher(FakeScreen()).definitions().map { it.name }
        assertTrue("usage_stats" in names)
    }
}
