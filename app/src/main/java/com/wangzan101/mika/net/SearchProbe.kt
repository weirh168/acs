package com.wangzan101.mika.net

import com.wangzan101.mika.core.search.WebSearch
import com.wangzan101.mika.core.search.WebSearchResult
import kotlinx.coroutines.withTimeoutOrNull

/**
 * 网页搜索能不能用:真发一次查询,而不是只测域名可达。
 * 搜索服务挂了、密钥失效、被限流,都会在这一次里暴露出来。
 */
object SearchProbe {
    /** 探测用的固定查询:短、通用、结果稳定。 */
    const val QUERY = "mika"

    suspend fun run(search: WebSearch, timeoutMs: Long = 8_000): ProbeResult {
        val start = System.currentTimeMillis()
        val result = withTimeoutOrNull(timeoutMs) {
            runCatching { search.search(QUERY, 1) }.getOrNull()
        }
        val elapsed = System.currentTimeMillis() - start
        return when {
            result == null -> ProbeResult(false, elapsed, "超时")
            result is WebSearchResult.Success -> ProbeResult(true, elapsed, "")
            result is WebSearchResult.Failure -> ProbeResult(false, elapsed, result.message.ifBlank { result.code })
            else -> ProbeResult(false, elapsed, "连不上")
        }
    }
}
