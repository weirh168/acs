package com.wangzan101.mika.core.usage

import com.wangzan101.mika.core.prompt.Feedback
import com.wangzan101.mika.core.prompt.Prompts
import com.wangzan101.mika.core.tool.AgentTool
import com.wangzan101.mika.core.tool.Args
import com.wangzan101.mika.core.tool.Concurrency
import com.wangzan101.mika.core.tool.Risk
import com.wangzan101.mika.core.tool.ToolContext
import com.wangzan101.mika.core.tool.ToolDef
import com.wangzan101.mika.core.tool.ToolExecution
import com.wangzan101.mika.core.tool.Verb
import com.wangzan101.mika.core.tool.ok
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject
import kotlin.coroutines.coroutineContext

/**
 * 看这次任务花了多少 token、还剩多少预算,以及今天整台手机用了多少。
 *
 * 本次的数来自运行自己的 [RunUsageTally](在协程上下文里,主循环和旁路调用都算在它名下);
 * 今天的数来自 App 侧的用量账本,端口没给就只有本次的。只读,不产生任何模型调用。
 */
internal object UsageStats : AgentTool {
    override val verb = Verb.SelfStatus
    override val label = "看用量"
    override val risk = Risk.Read
    override val concurrency = Concurrency.ParallelSafe
    override val offScreen = true

    override val def = ToolDef("usage_stats", Prompts.tool("usage_stats"), emptyMap(), emptyList())

    override suspend fun execute(a: Args, ctx: ToolContext): ToolExecution {
        val tally = coroutineContext[RunUsageTally]
        val today = runCatching { ctx.config.self?.usageToday() }.getOrNull()
        return ok {
            putJsonObject("run") {
                if (tally == null) {
                    put("available", false)
                    put("hint", Feedback["usage.run_unavailable"])
                } else {
                    put("available", true)
                    put("inputTokens", tally.inputTokens())
                    put("outputTokens", tally.outputTokens())
                    put("cachedInputTokens", tally.cachedTokens())
                    put("tokens", tally.totalTokens())
                    put("calls", tally.logicalCalls())
                    put("httpCalls", tally.httpCalls())
                    tally.tokenBudget?.let { budget ->
                        put("budget", budget)
                        put("remaining", (budget - tally.totalTokens()).coerceAtLeast(0))
                    }
                }
            }
            today?.let { t ->
                putJsonObject("today") {
                    put("tokens", t.tokens)
                    put("inputTokens", t.input)
                    put("outputTokens", t.output)
                    put("cachedInputTokens", t.cached)
                    put("calls", t.calls)
                }
            }
        }
    }
}
