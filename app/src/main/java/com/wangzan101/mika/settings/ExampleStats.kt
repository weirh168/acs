package com.wangzan101.mika.settings

import android.content.Context

/**
 * 首页「试试这样说」的点击计数:点得多的排前面。
 * 只记次数,不记内容以外的东西;卸载即清。
 */
object ExampleStats {
    private const val FILE = "example-stats"
    private const val KEY = "counts"

    /** 一条示例被点了多少次。 */
    fun count(context: Context, title: String): Int {
        val raw = prefs(context).getString(KEY, null) ?: return 0
        return raw.split(';').firstOrNull { it.startsWith("$title=") }
            ?.substringAfter('=')?.toIntOrNull() ?: 0
    }

    /** 记一次点击。 */
    fun hit(context: Context, title: String) {
        val prefs = prefs(context)
        val raw = prefs.getString(KEY, null).orEmpty()
        val entries = raw.split(';').filter { it.isNotBlank() }.associate { line ->
            line.substringBefore('=') to (line.substringAfter('=').toIntOrNull() ?: 0)
        }.toMutableMap()
        entries[title] = (entries[title] ?: 0) + 1
        prefs.edit().putString(KEY, entries.entries.joinToString(";") { "${it.key}=${it.value}" }).apply()
    }

    /** 按点击次数从高到低排;次数相同的保持原顺序。 */
    fun order(context: Context, titles: List<String>): List<String> =
        titles.sortedByDescending { count(context, it) }

    private fun prefs(context: Context) = context.getSharedPreferences(FILE, Context.MODE_PRIVATE)
}
