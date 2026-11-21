package com.wangzan101.mika.core.shell

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** 交接日志的落点:App 里写到文件,测试里可以收进内存。 */
interface HandoffJournalSink {
    fun write(line: String)
}

/**
 * 内置助手「交接」这一路的可读流水:谁先起了助手、口令有没有对上、交接有没有来、为什么被拒、看门狗第几次重试。
 * 这些信息以前只在 Logcat 里散着,用户拿不到;写成一份文件,出问题能直接看。
 *
 * 不记口令原文、不记 Binder、不记号码;只记事件名和少量数字(pid 之外的都不写)。
 */
object HandoffJournal {
    @Volatile
    private var sink: HandoffJournalSink? = null
    private val stamp = SimpleDateFormat("MM-dd HH:mm:ss.SSS", Locale.US)

    fun install(target: HandoffJournalSink?) {
        sink = target
    }

    fun note(event: String, detail: String = "") {
        val target = sink ?: return
        val line = format(event, detail)
        runCatching { target.write(line) }
    }

    private fun format(event: String, detail: String): String {
        val time = synchronized(stamp) { stamp.format(Date()) }
        return if (detail.isEmpty()) "$time $event" else "$time $event | $detail"
    }
}
