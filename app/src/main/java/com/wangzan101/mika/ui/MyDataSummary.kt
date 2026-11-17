package com.wangzan101.mika.ui

/**
 * 「我的数据」里的文案拼装。只做数字到人话的转换,不碰界面和存储。
 * 顺序固定为:有多少 → 是什么。0 条说「没有」,不显示「0 条」。
 */
data class MyDataCounts(
    val conversations: Int = 0,
    val memories: Int = 0,
    val logins: Int = 0,
    val learned: Int = 0,
)

object MyDataSummary {
    /** 子页顶部那一行:42 段对话 · 18 条记忆 · 3 个网站登录 */
    fun headline(counts: MyDataCounts): String = listOf(
        "${counts.conversations} 段对话",
        "${counts.memories} 条记忆",
        "${counts.logins} 个网站登录",
    ).joinToString(" · ")

    /** 设置页那一行的副标题:记住的事 18 条 · 登录网站 3 个 */
    fun rowSubtitle(counts: MyDataCounts): String {
        if (counts.memories == 0 && counts.logins == 0) return "还没有记住任何东西"
        val parts = buildList {
            add(if (counts.memories == 0) "记住的事 没有" else "记住的事 ${counts.memories} 条")
            if (counts.logins > 0) add("登录网站 ${counts.logins} 个")
        }
        return parts.joinToString(" · ")
    }

    /** 清单里每一行的右侧数字:有就写数量,没有就说「没有」 */
    fun count(value: Int, unit: String): String = if (value == 0) "没有" else "$value $unit"

    /** 学到的做法那一行:它自己总结的操作习惯 */
    fun learnedNote(counts: MyDataCounts): String =
        if (counts.learned == 0) "还没有总结出习惯" else "它自己总结的操作习惯"
}
