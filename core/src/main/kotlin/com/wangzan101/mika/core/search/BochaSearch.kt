package com.wangzan101.mika.core.search

import com.wangzan101.mika.core.net.NetProxy
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request

/**
 * 博查搜索(Bocha):`POST https://api.bochaai.com/v1/web-search`,`Authorization: Bearer <key>`,
 * 请求体 `{"query","count","summary":true}`。返回 `data.webPages.value[]` 里的 name/url/snippet。
 * 国内直连,不经过境外服务。
 */
class BochaSearch(
    apiKey: String,
    private val client: OkHttpClient = NetProxy.shared.client(),
    private val url: HttpUrl = URL.toHttpUrl(),
) : WebSearch {
    private val key = apiKey.trim()

    override suspend fun search(query: String, count: Int): WebSearchResult {
        val n = count.coerceIn(1, WebSearch.MAX_COUNT)
        val body = buildJsonObject {
            put("query", query)
            put("count", n)
            put("summary", true)
        }
        val request = Request.Builder().url(url).header("Authorization", "Bearer $key").post(SearchHttp.json(body)).build()
        return SearchHttp.call(client, request) { root -> parse(root, n) }
    }

    private fun parse(root: JsonObject, count: Int): WebSearchResult {
        val value = ((root["data"] as? JsonObject)?.get("webPages") as? JsonObject)?.get("value") as? JsonArray
            ?: return WebSearchResult.Failure("invalid_response", "The Bocha response has no webPages.")
        return WebSearchResult.Success(value.mapNotNull { item ->
            val o = item as? JsonObject ?: return@mapNotNull null
            SearchHttp.hit(SearchHttp.text(o, "name"), SearchHttp.text(o, "url"), SearchHttp.text(o, "snippet"))
        }.take(count))
    }

    companion object {
        const val URL = "https://api.bochaai.com/v1/web-search"
    }
}
