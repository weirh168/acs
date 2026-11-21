package com.wangzan101.mika.cap.phone.shell

import android.content.Context
import com.wangzan101.mika.core.shell.HandoffJournalSink
import java.io.File

/**
 * 交接日志写到 files/handoff.log:只留最近一段,免得越积越大。
 * 用户能把这份文件导出来(设置里的诊断也会带最后几十行),交接失败时不用再猜。
 */
internal class HandoffLogFile(context: Context) : HandoffJournalSink {
    private val file = File(context.applicationContext.filesDir, NAME)

    override fun write(line: String) {
        synchronized(this) {
            runCatching {
                val kept = if (file.exists()) file.readText().takeLast(MAX_CHARS) else ""
                file.writeText(kept + line + "\n")
            }
        }
    }

    /** 供诊断页面读:最后 [lines] 行,新的在后面。 */
    fun tail(lines: Int): List<String> = synchronized(this) {
        if (!file.exists()) return emptyList()
        runCatching { file.readLines().takeLast(lines) }.getOrDefault(emptyList())
    }

    private companion object {
        const val NAME = "handoff.log"
        const val MAX_CHARS = 200_000
    }
}
