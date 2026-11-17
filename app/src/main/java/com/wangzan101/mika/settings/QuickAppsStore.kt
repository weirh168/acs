package com.wangzan101.mika.settings

import android.content.Context

/**
 * 首页「直接打开」里那几个 App:顺序由用户决定,存在这台手机上。
 * 第一次读时用 [DEFAULTS] 的顺序;用户长按某个 App 就把它提到最前面。
 */
object QuickAppsStore {
    private const val FILE = "quick-apps"
    private const val KEY = "order"

    /** 默认候选:只列出常见的那几个,装了才显示。 */
    val DEFAULTS = listOf(
        "com.tencent.mm" to "微信",
        "com.xingin.xhs" to "小红书",
        "com.eg.android.AlipayGphone" to "支付宝",
        "com.autonavi.minimap" to "高德",
        "com.ss.android.ugc.aweme" to "抖音",
        "com.tencent.mobileqq" to "QQ",
        "com.taobao.taobao" to "淘宝",
        "com.jingdong.app.mall" to "京东",
        "me.ele" to "饿了么",
        "com.sankuai.meituan" to "美团",
        "com.netease.cloudmusic" to "网易云音乐",
        "tv.danmaku.bili" to "哔哩哔哩",
        "com.zhihu.android" to "知乎",
        "com.larus.nova" to "豆包",
        "com.deepseek.chat" to "DeepSeek",
    )

    private fun prefs(context: Context) = context.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    /** 用户排好的顺序;没存过时是默认顺序。 */
    fun order(context: Context): List<String> {
        val saved = prefs(context).getString(KEY, null)
            ?.split(',')?.filter { it.isNotBlank() }.orEmpty()
        if (saved.isEmpty()) return DEFAULTS.map { it.first }
        // 默认池里有、但用户顺序里漏掉的,补在后面,免得升级后新 App 永远不出现
        return saved + DEFAULTS.map { it.first }.filter { it !in saved }
    }

    /**
     * 长按某个 App:把它挪到队尾,这一格就换成池子里的另一个。
     * 反复长按会不断换新,原来的 App 不会被删掉,只是排到后面。
     */
    fun rotateOut(context: Context, packageName: String) {
        val current = order(context).toMutableList()
        if (current.size < 2) return
        current.remove(packageName)
        prefs(context).edit().putString(KEY, (current + packageName).joinToString(",")).apply()
    }

    /** 用户自己加一个 App:排到最前面,以后就在首页上。 */
    fun pinToFront(context: Context, packageName: String, label: String) {
        extras(context).let { if (label.isNotBlank()) it.edit().putString(packageName, label).apply() }
        val current = order(context).toMutableList()
        current.remove(packageName)
        prefs(context).edit().putString(KEY, (listOf(packageName) + current).joinToString(",")).apply()
    }

    private fun extras(context: Context) = context.getSharedPreferences(FILE + "-labels", Context.MODE_PRIVATE)

    fun labelOf(context: Context, packageName: String): String =
        DEFAULTS.firstOrNull { it.first == packageName }?.second
            ?: extras(context).getString(packageName, null)
            ?: packageName
}
