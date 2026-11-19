package com.wangzan101.mika.core.agent

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/**
 * 兜底:有的模型不真正调用工具,而是把调用写成文本,例如
 * `<acs_draw prompt="一只小花猫">`、`<acs_video>{"prompt":"…"}</acs_video>`、
 * `<acs_draw>一只小花猫</acs_draw>`。这里认出来并换成真正的工具调用,回答里那段标签去掉。
 */
object PseudoTool {
    /** [name] 工具名;[argsJson] 参数;[left] 去掉标签后的正文。 */
    data class Found(val name: String, val argsJson: String, val left: String)

    /** 认识的工具名(和真工具同名)。 */
    private val NAMES = listOf("acs_draw", "acs_video")
    private val TAG = Regex(
        """<\s*(acs_draw|acs_video)\b([^>]*)>(.*?)(?:<\s*/\s*\1\s*>|$)""",
        setOf(RegexOption.DOT_MATCHES_ALL, RegexOption.IGNORE_CASE),
    )
    private val SELF_CLOSING = Regex(
        """<\s*(acs_draw|acs_video)\b([^>]*?)/\s*>""",
        setOf(RegexOption.DOT_MATCHES_ALL, RegexOption.IGNORE_CASE),
    )
    private val PROMPT = Regex("""prompt\s*=\s*("([^"]*)"|'([^']*)')""", RegexOption.IGNORE_CASE)

    fun parse(text: String): Found? {
        SELF_CLOSING.find(text)?.let { m ->
            val name = m.groupValues[1].lowercase()
            val prompt = attrPrompt(m.groupValues[2]) ?: return@let
            return Found(name, argsOf(prompt), (text.removeRange(m.range)).trim())
        }
        val m = TAG.find(text) ?: return null
        val name = m.groupValues[1].lowercase()
        if (name !in NAMES) return null
        val inner = m.groupValues[2 + 1].trim()
        val args = when {
            inner.startsWith("{") -> runCatching {
                val o = Json.parseToJsonElement(inner).jsonObject
                Json.encodeToString(JsonObject.serializer(), o)
            }.getOrNull()
            else -> null
        } ?: attrPrompt(m.groupValues[2])?.let(::argsOf)
            ?: inner.takeIf { it.isNotBlank() && !it.startsWith("{") }?.let(::argsOf)
            ?: return null
        return Found(name, args, (text.removeRange(m.range)).trim())
    }

    private fun attrPrompt(attrs: String): String? =
        PROMPT.find(attrs)?.let { it.groupValues[2].takeIf(String::isNotEmpty) ?: it.groupValues[3] }
            ?.takeIf { it.isNotBlank() }

    private fun argsOf(prompt: String): String =
        Json.encodeToString(JsonObject.serializer(), buildJsonObject { put("prompt", prompt) })
}