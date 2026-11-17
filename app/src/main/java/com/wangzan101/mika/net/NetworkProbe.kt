package com.wangzan101.mika.net

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

/** 一次连通性探测的结果。失败也给结论,不抛异常。 */
data class ProbeResult(val reachable: Boolean, val elapsedMs: Long, val detail: String) {
    companion object {
        /** 界面直接用这句话:成功给耗时,失败给原因。 */
        fun summary(result: ProbeResult): String =
            if (result.reachable) "${result.elapsedMs / 1000.0} 秒" else result.detail
    }
}

/** 只问一句「这个地址现在通不通」:HEAD 请求、5 秒超时,不下载响应体。 */
object NetworkProbe {
    suspend fun head(
        url: String,
        timeoutMs: Int = 5_000,
        accept: (Int) -> Boolean = { it in 200..399 },
    ): ProbeResult = withContext(Dispatchers.IO) {
        val start = System.currentTimeMillis()
        var connection: HttpURLConnection? = null
        try {
            connection = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "HEAD"
                connectTimeout = timeoutMs
                readTimeout = timeoutMs
                instanceFollowRedirects = true
                setRequestProperty("User-Agent", "Mika-NetProbe")
            }
            val code = connection.responseCode
            val elapsed = System.currentTimeMillis() - start
            if (accept(code)) ProbeResult(true, elapsed, "") else ProbeResult(false, elapsed, "HTTP $code")
        } catch (e: java.net.SocketTimeoutException) {
            ProbeResult(false, System.currentTimeMillis() - start, "超时")
        } catch (e: Exception) {
            ProbeResult(false, System.currentTimeMillis() - start, "连不上")
        } finally {
            runCatching { connection?.disconnect() }
        }
    }
}

