package com.wangzan101.mika.calls

import android.content.Context
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 只写「为什么没接」这类判定痕迹，不记号码原文、不记转写内容。
 * 文件有上限，旧的自动截断，用户可以在设置里清空。
 */
internal object CallDebugLog {
    private const val NAME = "call-debug.log"
    private const val MAX_CHARS = 120_000
    private val stamp = SimpleDateFormat("MM-dd HH:mm:ss.SSS", Locale.US)

    @Synchronized
    fun note(context: Context, tag: String, message: String) {
        runCatching {
            val file = File(context.filesDir, NAME)
            val line = "${stamp.format(Date())} [$tag] $message\n"
            val kept = if (file.exists()) file.readText().takeLast(MAX_CHARS) else ""
            file.writeText(kept + line)
        }
    }

    fun clear(context: Context) {
        runCatching { File(context.filesDir, NAME).delete() }
    }
}
