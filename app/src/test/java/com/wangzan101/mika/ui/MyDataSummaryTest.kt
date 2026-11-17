package com.wangzan101.mika.ui

import org.junit.Assert.assertEquals
import org.junit.Test

class MyDataSummaryTest {
    @Test fun headlineListsTheThreeCounts() {
        assertEquals(
            "42 段对话 · 18 条记忆 · 3 个网站登录",
            MyDataSummary.headline(MyDataCounts(conversations = 42, memories = 18, logins = 3)),
        )
    }

    @Test fun rowSubtitleReadsLikeABookkeepingLine() {
        assertEquals(
            "记住的事 18 条 · 登录网站 3 个",
            MyDataSummary.rowSubtitle(MyDataCounts(memories = 18, logins = 3)),
        )
    }

    @Test fun emptySaysNothingRememberedInsteadOfZero() {
        assertEquals("还没有记住任何东西", MyDataSummary.rowSubtitle(MyDataCounts()))
        assertEquals("没有", MyDataSummary.count(0, "条"))
        assertEquals("12 条", MyDataSummary.count(12, "条"))
        assertEquals("还没有总结出习惯", MyDataSummary.learnedNote(MyDataCounts()))
        assertEquals("它自己总结的操作习惯", MyDataSummary.learnedNote(MyDataCounts(learned = 5)))
    }
}
