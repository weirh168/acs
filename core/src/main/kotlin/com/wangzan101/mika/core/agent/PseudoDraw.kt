package com.wangzan101.mika.core.agent

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/**
 * 兜底:有的模型不真正调用工具,而是把调用写成文本,例如
 * `<acs_draw prompt="一只小花猫">` 或 `<acs_draw prompt='…'></acs_draw>`。
 * 这里把它认出来,换成真正的工具调用,回答里那段标签去掉。
 */
object PseudoDraw {
    /** 找到的伪调用:[argsJson] 给工具用,[left] 是去掉标签以后剩下的正文。 */
    data class Found(val argsJson: String, val left: String)

    private val TAG = Regex("""<\s*acs_draw\b([^>]*)>(.*?)(?:<\s*/\s*acs_draw\s*>)?$""", setOf(RegexOption.DOT_MATCHES_ALL, RegexOption.IGNORE_CASE))
    private val PROMPT = Regex("""prompt\s*=\s*("([^"]*)"|'([^']*)')""", RegexOption.IGNORE_CASE)

    fun parse(text: String): Found? {
        val m = TAG.find(text) ?: return null
        val attrs = m.groupValues[1]
        val inner = m.groupValues[2].trim()
        val prompt = PROMPT.find(attrs)?.let { it.groupValues[2].takeIf(String::isNotEmpty) ?: it.groupValues[3] }
            ?.takeIf { it.isNotBlank() }
            ?: inner.takeIf { it.isNotBlank() }
            ?: return null
        val left = (text.removeRange(m.range)).trim()
        val args = buildJsonObject { put("prompt", prompt) }
        return Found(Json.encodeToString(kotlinx.serialization.json.JsonObject.serializer(), args), left)
    }
}