package com.wangzan101.mika.calls

import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.MediaType.Companion.toMediaType
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec
import java.time.ZoneOffset
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

/**
 * 火山引擎「智能外呼」客户端:把一通电话交给云端的 AI 会话机器人去打。
 *
 * 走的是官方 OpenAPI(`volc_voice_robot` / `2021-01-01`),需要 V4 签名;
 * 语音对话发生在云端(电话通道 + 大模型),所以本机不需要任何通话音频权限 ——
 * 这正是绕开「荣耀不允许第三方注入通话音频」的做法。
 */
object CloudCall {
    private const val HOST = "open.volcengineapi.com"
    private const val SERVICE = "volc_voice_robot"
    private const val REGION = "cn-north-1"
    private const val VERSION = "2021-01-01"
    private const val CONFIG = "cloudcall.json"

    /** appId 用不上;这里只要 AK/SK + 号码池 + 话术 + 外显号。 */
    data class Config(
        val accessKey: String,
        val secretKey: String,
        val numberPoolNo: String,
        val script: String,
        val callerNumber: String,
    ) {
        val ready: Boolean get() = accessKey.isNotBlank() && secretKey.isNotBlank() &&
            numberPoolNo.isNotBlank() && script.isNotBlank() && callerNumber.isNotBlank()
    }

    fun load(app: android.content.Context): Config? = runCatching {
        val f = File(app.filesDir, "settings/$CONFIG")
        if (!f.exists()) return null
        val j = JSONObject(f.readText())
        Config(
            j.optString("accessKey"), j.optString("secretKey"),
            j.optString("numberPoolNo"), j.optString("script"), j.optString("callerNumber"),
        )
    }.getOrNull()

    fun save(app: android.content.Context, config: Config) {
        val f = File(app.filesDir, "settings/$CONFIG")
        f.parentFile?.mkdirs()
        f.writeText(
            JSONObject().apply {
                put("accessKey", config.accessKey)
                put("secretKey", config.secretKey)
                put("numberPoolNo", config.numberPoolNo)
                put("script", config.script)
                put("callerNumber", config.callerNumber)
            }.toString(),
        )
    }

    /** 建一个只打一个号码、立刻开始的任务。返回 TaskId 或错误文字。 */
    fun createTask(app: android.content.Context, phone: String): String {
        val config = load(app) ?: return "还没配置云电话(缺 AK/SK 或号码池)"
        if (!config.ready) return "云电话配置不完整"
        val body = JSONObject().apply {
            put("Name", "acs-" + System.currentTimeMillis())
            put("PhoneList", JSONArray().put(JSONObject().put("Phone", phone)))
            put("Script", config.script)
            put("NumberPoolNo", config.numberPoolNo)
            put("NumberList", JSONArray().put(config.callerNumber))
            val now = ZonedDateTime.now(ZoneOffset.ofHours(8))
            val fmt = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")
            put("StartTime", now.format(fmt))
            put("EndTime", now.plusMinutes(10).format(fmt))
            put("Concurrency", 1)
            put("Unique", false)
        }.toString()
        return post("CreateTask", body)
    }

    private fun post(action: String, body: String): String = runCatching {
        val query = "Action=$action&Version=$VERSION"
        val signed = sign(body, query)
        val request = Request.Builder()
            .url("https://$HOST/?$query")
            .addHeader("X-Date", signed.date)
            .addHeader("Authorization", signed.authorization)
            .addHeader("X-Content-Sha256", signed.bodyHash)
            .addHeader("Content-Type", "application/json")
            .post(body.toRequestBody("application/json".toMediaType()))
            .build()
        val response = OkHttpClient().newCall(request).execute()
        val text = response.body?.string().orEmpty()
        if (!response.isSuccessful) "云电话失败(" + response.code + "):" + text.take(200)
        else {
            val json = JSONObject(text)
            val result = json.optJSONObject("Result")
            val id = result?.optString("TaskId").orEmpty()
            if (id.isNotBlank()) "已交给云端 AI 拨打:" + phoneLabel + "(任务 " + id + ")" else text.take(300)
        }
    }.getOrElse { "云电话出错:" + (it.message ?: it.javaClass.simpleName) }

    private var phoneLabel = ""

    private data class Signed(val date: String, val authorization: String, val bodyHash: String)

    /** 火山引擎 V4 签名(与官方 SDK 等价的最小实现)。 */
    private fun sign(body: String, query: String): Signed {
        val config = requireNotNull(load(appForSign)) { "no config" }
        val now = ZonedDateTime.now(ZoneOffset.UTC)
        val date = now.format(DateTimeFormatter.ofPattern("yyyyMMdd'T'HHmmss'Z'"))
        val shortDate = date.substring(0, 8)
        val bodyHash = sha256Hex(body)
        val canonicalQuery = query.split("&").sorted().joinToString("&")
        val canonicalHeaders = "content-type:application/json\nhost:$HOST\nx-content-sha256:$bodyHash\nx-date:$date\n"
        val signedHeaders = "content-type;host;x-content-sha256;x-date"
        val canonicalRequest = listOf("POST", "/", canonicalQuery, canonicalHeaders, signedHeaders, bodyHash).joinToString("\n")
        val scope = "$shortDate/$REGION/$SERVICE/request"
        val stringToSign = listOf("HMAC-SHA256", date, scope, sha256Hex(canonicalRequest)).joinToString("\n")
        val kDate = hmac(("VOLC" + config.secretKey).toByteArray(), shortDate)
        val kRegion = hmac(kDate, REGION)
        val kService = hmac(kRegion, SERVICE)
        val kSigning = hmac(kService, "request")
        val signature = hmac(kSigning, stringToSign).toHex()
        val authorization = "HMAC-SHA256 Credential=" + config.accessKey + "/" + scope +
            ", SignedHeaders=" + signedHeaders + ", Signature=" + signature
        return Signed(date, authorization, bodyHash)
    }

    @Volatile
    private lateinit var appForSign: android.content.Context

    fun remember(app: android.content.Context) { appForSign = app.applicationContext }

    private fun sha256Hex(text: String): String =
        MessageDigest.getInstance("SHA-256").digest(text.toByteArray()).toHex()

    private fun hmac(key: ByteArray, data: String): ByteArray {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(key, "HmacSHA256"))
        return mac.doFinal(data.toByteArray())
    }

    private fun ByteArray.toHex(): String = joinToString("") { "%02x".format(it) }
}