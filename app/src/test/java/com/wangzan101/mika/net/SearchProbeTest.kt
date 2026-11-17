package com.wangzan101.mika.net

import com.wangzan101.mika.core.search.WebSearch
import com.wangzan101.mika.core.search.WebSearchHit
import com.wangzan101.mika.core.search.WebSearchResult
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SearchProbeTest {
    private class Fake(private val result: WebSearchResult) : WebSearch {
        override suspend fun search(query: String, count: Int): WebSearchResult = result
    }

    @Test fun successReportsATiming() = runBlocking {
        val r = SearchProbe.run(Fake(WebSearchResult.Success(listOf(WebSearchHit("t", "u", "s")))))
        assertTrue(r.reachable)
        assertTrue(ProbeResult.summary(r).endsWith("秒"))
    }

    @Test fun failureReportsTheServiceMessage() = runBlocking {
        val r = SearchProbe.run(Fake(WebSearchResult.Failure("quota", "额度用完了")))
        assertEquals("额度用完了", ProbeResult.summary(r))
    }

    @Test fun thrownErrorBecomesUnreachable() = runBlocking {
        val boom = object : WebSearch {
            override suspend fun search(query: String, count: Int): WebSearchResult = error("boom")
        }
        assertEquals("超时", ProbeResult.summary(SearchProbe.run(boom)))
    }
}
