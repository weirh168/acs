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
 * 生图的落地实现：读 settings/imagegen.json 取模型与地址，Key 按 providerId 从服务商配置里解密取。
 * 生成后存两处：相册 Pictures/ACS（给人看）、沙箱 inbox（给对话当附件）。
 */
object ImageDraw {
    private val http = OkHttpClient()
    private const val FALLBACK_MODEL = "agnes-image-2.5-flash"
    private const val FALLBACK_BASE = "https://api.agnes-ai.cn/v1"
    private const val SIZE = 1024

    private data class Cfg(val model: String, val baseUrl: String, val providerId: String?)

    private fun cfg(app: MikaApp): Cfg {
        // AI 引擎里选的「生图模型」是唯一真相:重启后还在,Key 也按这条配置的服务商取
        val store = app.providers
        val role = runCatching { store.configFor(ModelRole.Image) }.getOrNull()
        if (role != null) {
            val provider = role.providerId.takeIf { it.isNotBlank() }?.let { store.provider(it) }
            val key = store.apiKey(role.id) ?: role.providerId.takeIf { it.isNotBlank() }?.let { store.providerKey(it) }
            if (!key.isNullOrBlank()) {
                val base = (provider?.baseUrl ?: role.baseUrl).ifBlank { FALLBACK_BASE }
                return Cfg(role.model, base.trimEnd('/'), role.providerId.takeIf { it.isNotBlank() })
            }
        }
        val f = File(app.filesDir, "settings/imagegen.json")
        val o = runCatching { Json.parseToJsonElement(f.readText()).jsonObject }.getOrNull()
        val model = o?.get("model")?.jsonPrimitive?.content?.takeIf { it.isNotBlank() } ?: FALLBACK_MODEL
        val base = o?.get("baseUrl")?.jsonPrimitive?.content?.takeIf { it.isNotBlank() } ?: FALLBACK_BASE
        val pid = o?.get("providerId")?.jsonPrimitive?.content?.takeIf { it.isNotBlank() }
        return Cfg(model, base.trimEnd('/'), pid)
    }

    /** 用户没说风格时补摄影词；说了风格就尊重原话。 */
    private val STYLE = Regex("水彩|油画|素描|插画|卡通|动漫|扁平|像素|3D|赛博|国潮|水墨|写实|摄影|风格|logo|标志")
    fun enhance(prompt: String): String =
        if (STYLE.containsMatchIn(prompt)) prompt
        else prompt + ",高清摄影风格,自然光,浅景深,细节丰富,构图讲究"

    suspend fun draw(app: MikaApp, conversationId: String, prompt: String): com.wangzan101.mika.core.cap.imagegen.ImageGenResult = withContext(Dispatchers.IO) {
        val c = cfg(app)
        val key = c.providerId?.let { app.providers.providerKey(it) }.orEmpty()
        if (key.isBlank()) return@withContext com.wangzan101.mika.core.cap.imagegen.ImageGenResult("生图模型的 Key 取不到,请在 AI 引擎里重新选一次生图模型。", null)
        val body = buildJsonObject {
            put("model", c.model)
            put("prompt", enhance(prompt))
            put("n", 1)
            put("size", SIZE.toString() + "x" + SIZE.toString())
        }.toString().toRequestBody("application/json".toMediaType())
        val req = Request.Builder().url(c.baseUrl + "/images/generations")
            .addHeader("Authorization", "Bearer " + key).post(body).build()
        val json = http.newCall(req).execute().use { r ->
            val text = r.body?.string().orEmpty()
            if (!r.isSuccessful) return@withContext com.wangzan101.mika.core.cap.imagegen.ImageGenResult("生图失败(HTTP " + r.code + "): " + text.take(200), null)
            Json.parseToJsonElement(text).jsonObject
        }
        val imageUrl = (json["data"] as? JsonArray)?.firstOrNull()
            ?.jsonObject?.get("url")?.jsonPrimitive?.content
        if (imageUrl == null) return@withContext com.wangzan101.mika.core.cap.imagegen.ImageGenResult("生图接口没返回图片地址", null)
        val bytes = http.newCall(Request.Builder().url(imageUrl).build()).execute().use { r -> r.body?.bytes() }
        if (bytes == null) return@withContext com.wangzan101.mika.core.cap.imagegen.ImageGenResult("图片下载失败", null)
        val name = "draw_" + System.currentTimeMillis() + ".png"
        saveToGallery(app, bytes, name)
        saveToWorkspace(app, conversationId, bytes, name)
        // 末尾带上「附件:」那一行:对话页据此把这张图直接画成可点开的图片,而不是只给一句文字
        val label = com.wangzan101.mika.core.agent.AttachmentLines.sizeLabel(bytes.size.toLong())
        val line = com.wangzan101.mika.core.agent.AttachmentLines.line("/workspace/inbox/" + name, label)
        com.wangzan101.mika.core.cap.imagegen.ImageGenResult(
            "画好了,已存到相册 Pictures/ACS/" + name + "(" + label + ")\n" + line,
            bytes,
        )
    }

    private fun saveToGallery(context: Context, bytes: ByteArray, name: String) {
        runCatching {
            val values = ContentValues().apply {
                put(MediaStore.Images.Media.DISPLAY_NAME, name)
                put(MediaStore.Images.Media.MIME_TYPE, "image/png")
                put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/ACS")
                put(MediaStore.Images.Media.IS_PENDING, 1)
            }
            val uri = context.contentResolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values) ?: return
            context.contentResolver.openOutputStream(uri)?.use { it.write(bytes) }
            values.clear()
            values.put(MediaStore.Images.Media.IS_PENDING, 0)
            context.contentResolver.update(uri, values, null, null)
        }
    }

    /** 存进这个对话的工作区 inbox:对话页按 /workspace/inbox/<名字> 找得到这张图,能直接显示。 */
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
