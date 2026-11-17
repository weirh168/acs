package com.wangzan101.mika.mydata

import android.content.Context
import com.wangzan101.mika.MikaApp
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/**
 * 导出「我的数据」:只导元数据(条数、标题、域名、时间),不导对话正文与密钥。
 * 写到 App 自己的外部目录,用户可以用文件管理器发给别人;暂不走系统分享。
 */
object MyDataExporter {
    suspend fun export(context: Context): File? = runCatching {
        val app = context.applicationContext as MikaApp
        val root = JSONObject()
        root.put("exportedAt", System.currentTimeMillis())

        val memories = app.memory.items().value
        root.put("memories", JSONArray().apply {
            memories.forEach { put(JSONObject().put("text", it.content.take(200))) }
        })

        val conversations = app.conversations.list()
        root.put("conversations", JSONArray().apply {
            conversations.forEach { put(JSONObject().put("title", it.title).put("updatedAt", it.updatedAt)) }
        })

        root.put("sites", JSONArray().apply {
            app.webSites.list().forEach { put(JSONObject().put("host", it.host).put("loggedIn", it.loggedInByUser)) }
        })

        val dir = context.getExternalFilesDir("exports") ?: return null
        dir.mkdirs()
        val file = File(dir, "mika-data-" + System.currentTimeMillis() + ".json")
        file.writeText(root.toString(2))
        file
    }.getOrNull()
}


