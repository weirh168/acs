package com.wangzan101.mika.cap

import android.content.ContentValues
import android.content.Context
import android.os.Environment
import android.provider.MediaStore
import com.wangzan101.mika.MikaApp
import com.wangzan101.mika.core.model.ModelRole
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File

/**
 * 生视频的落地实现:读 settings/videogen.json 取模型、地址和 mode,Key 按 providerId 解密取。
 * 平台没放行时(403 / Model is blocked)返回一句人话,由模型改走别的办法。
 */
object VideoDraw {
    private val http = OkHttpClient()
    private const val FALLBACK_MODEL = "agnes-video-2.5-flash"
    private const val FALLBACK_BASE = "https://api.agnes-ai.cn/v1"

    private data class Cfg(
        val model: String, val baseUrl: String, val providerId: String?, val mode: String, val disabled: Boolean,
    )

    private fun cfg(app: MikaApp): Cfg {
        // 同生图:AI 引擎里选的那条配置优先,重启不用重配
        val store = app.providers
        val role = runCatching { store.configFor(ModelRole.Video) }.getOrNull()
        if (role != null) {
            val provider = role.providerId.takeIf { it.isNotBlank() }?.let { store.provider(it) }
            val key = store.apiKey(role.id) ?: role.providerId.takeIf { it.isNotBlank() }?.let { store.providerKey(it) }
            if (!key.isNullOrBlank()) {
                val base = (provider?.baseUrl ?: role.baseUrl).ifBlank { FALLBACK_BASE }
                return Cfg(role.model, base.trimEnd('/'), role.providerId.takeIf { it.isNotBlank() },
                    mode = "text-to-video", disabled = false)
            }
        }
        val f = File(app.filesDir, "settings/videogen.json")
        val o = runCatching { Json.parseToJsonElement(f.readText()).jsonObject }.getOrNull()
        val model = o?.get("model")?.jsonPrimitive?.content?.takeIf { it.isNotBlank() } ?: FALLBACK_MODEL
        val base = o?.get("baseUrl")?.jsonPrimitive?.content?.takeIf { it.isNotBlank() } ?: FALLBACK_BASE
        val pid = o?.get("providerId")?.jsonPrimitive?.content?.takeIf { it.isNotBlank() }
        val mode = o?.get("mode")?.jsonPrimitive?.content?.takeIf { it.isNotBlank() } ?: "text-to-video"
        val disabled = o?.get("disabled")?.jsonPrimitive?.content?.equals("true", true) == true
        return Cfg(model, base.trimEnd('/'), pid, mode, disabled)
    }

    suspend fun make(app: MikaApp, conversationId: String, prompt: String): com.wangzan101.mika.core.cap.imagegen.ImageGenResult =
        withContext(Dispatchers.IO) {
            val c = cfg(app)
            // 平台没放行(以前试过 403)时不打网络请求,直接让模型走手机 App,省时间也省额度
            if (c.disabled) return@withContext com.wangzan101.mika.core.cap.imagegen.ImageGenResult(
                "AGNES 视频模型还没放行(之前返回 403)。直接用手机上的即梦做:" +
                    "打开即梦 → 点底部「+」→ 输入这段描述 → 点生成 → 等出片后在「我的/作品」里找,把位置告诉用户。",
                null)
            val key = c.providerId?.let { app.providers.providerKey(it) }.orEmpty()
            if (key.isBlank()) return@withContext com.wangzan101.mika.core.cap.imagegen.ImageGenResult(
                "生视频模型的 Key 取不到,请在 AI 引擎里重新选一次生视频模型。", null)
            val body = buildJsonObject {
                put("model", c.model)
                put("prompt", prompt)
                put("mode", c.mode)
            }.toString().toRequestBody("application/json".toMediaType())
            val req = Request.Builder().url(c.baseUrl + "/video/generations")
                .addHeader("Authorization", "Bearer " + key).post(body).build()
            val text = http.newCall(req).execute().use { r ->
                val t = r.body?.string().orEmpty()
                if (!r.isSuccessful) {
                    val blocked = t.contains("blocked", true) || t.contains("PermissionDenied", true)
                    val why = if (blocked) "AGNES 视频模型还没放行(权限被拒)" else "生视频失败(HTTP " + r.code + ")"
                    return@withContext com.wangzan101.mika.core.cap.imagegen.ImageGenResult(
                        why + ":" + t.take(200) + "\n可以改用手机上的即梦/剪映来生成。", null)
                }
                t
            }
            val json = runCatching { Json.parseToJsonElement(text).jsonObject }.getOrNull()
            val url = (json?.get("data") as? JsonArray)?.firstOrNull()
                ?.jsonObject?.get("url")?.jsonPrimitive?.content
                ?: json?.get("video_url")?.jsonPrimitive?.content
            if (url == null) return@withContext com.wangzan101.mika.core.cap.imagegen.ImageGenResult(
                "接口没返回视频地址(可能还在生成中):" + text.take(200), null)
            val bytes = http.newCall(Request.Builder().url(url).build()).execute().use { r -> r.body?.bytes() }
            if (bytes == null) return@withContext com.wangzan101.mika.core.cap.imagegen.ImageGenResult("视频下载失败", null)
            val name = "video_" + System.currentTimeMillis() + ".mp4"
            saveToGallery(app, bytes, name)
            saveToWorkspace(app, conversationId, bytes, name)
            com.wangzan101.mika.core.cap.imagegen.ImageGenResult(
                "视频做好了,已存到相册 Movies/ACS/" + name + "(" + bytes.size / 1024 + " KB)", null)
        }

    private fun saveToGallery(context: Context, bytes: ByteArray, name: String) {
        runCatching {
            val values = ContentValues().apply {
                put(MediaStore.Video.Media.DISPLAY_NAME, name)
                put(MediaStore.Video.Media.MIME_TYPE, "video/mp4")
                put(MediaStore.Video.Media.RELATIVE_PATH, Environment.DIRECTORY_MOVIES + "/ACS")
                put(MediaStore.Video.Media.IS_PENDING, 1)
            }
            val uri = context.contentResolver.insert(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, values) ?: return
            context.contentResolver.openOutputStream(uri)?.use { it.write(bytes) }
            values.clear()
            values.put(MediaStore.Video.Media.IS_PENDING, 0)
            context.contentResolver.update(uri, values, null, null)
        }
    }

    private fun saveToWorkspace(app: MikaApp, conversationId: String, bytes: ByteArray, name: String) {
        runCatching {
            val safe = if (Regex("^[A-Za-z0-9_-]{1,100}$").matches(conversationId)) "c-" + conversationId else "h-" + conversationId
            for (dir in listOf(File(app.filesDir, "sandbox/work/" + safe + "/inbox"), File(app.filesDir, "sandbox/inbox"))) {
                dir.mkdirs()
                File(dir, name).writeBytes(bytes)
            }
        }
    }
}