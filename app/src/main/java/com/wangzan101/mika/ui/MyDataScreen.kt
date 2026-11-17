package com.wangzan101.mika.ui

import com.wangzan101.mika.ui.components.PageScaffold
import com.wangzan101.mika.ui.components.RowValue
import com.wangzan101.mika.ui.components.RowChevron
import com.wangzan101.mika.ui.components.ListRow
import com.wangzan101.mika.ui.components.GroupCard

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.wangzan101.mika.ui.theme.MikaTheme

/**
 * 「它记得我什么」子页:先答四个问题——有多少、是什么、怎么导走、怎么删。
 * 数据由调用方传入,本页只负责摆位置和文案。
 */
@Composable
fun MyDataScreen(
    counts: MyDataCounts,
    onBack: () -> Unit,
    onManageMemories: () -> Unit = {},
    onManageLearned: () -> Unit = {},
    onManageLogins: () -> Unit = {},
    onManageConversations: () -> Unit = {},
    onExport: () -> Unit = {},
    onClearAll: () -> Unit = {},
) {
    PageScaffold("它记得我什么", onBack) {
        Text(
            MyDataSummary.headline(counts),
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.padding(horizontal = 4.dp),
        )
        Text(
            "都只存在这台手机上，不会上传",
            fontSize = 13.sp,
            color = MikaTheme.colors.ink3,
            modifier = Modifier.padding(start = 4.dp, bottom = 8.dp),
        )
        GroupCard {
            DataRow("记住的事", "你说过的偏好、地址", MyDataSummary.count(counts.memories, "条"),
                first = true, onClick = onManageMemories)
            DataRow("学到的做法", MyDataSummary.learnedNote(counts), MyDataSummary.count(counts.learned, "条"),
                onClick = onManageLearned)
            DataRow("登录过的网站", "有过期时在这里重新登录", MyDataSummary.count(counts.logins, "个"),
                onClick = onManageLogins)
            DataRow("对话记录", "能看、能删、能导出", MyDataSummary.count(counts.conversations, "段"),
                onClick = onManageConversations)
        }
        Column(Modifier.fillMaxWidth().padding(top = 12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            ListRow(null, "导出我的数据", "打包成文件，自己保存或发给客服", first = true, onClick = onExport) { RowChevron() }
        }
        Column(Modifier.fillMaxWidth().padding(top = 12.dp)) {
            ListRow(
                null, "清空全部我的数据", "只删记忆与登录，不影响通话记录",
                first = true, titleColor = MikaTheme.colors.bad, onClick = onClearAll,
            ) { RowChevron() }
        }
        Text(
            "删掉后 AI 会重新认识你，不会影响已经接过的电话",
            fontSize = 13.sp,
            color = MikaTheme.colors.ink3,
            modifier = Modifier.padding(horizontal = 4.dp, vertical = 8.dp),
        )
    }
}

@Composable
private fun DataRow(title: String, note: String, value: String, first: Boolean = false, onClick: () -> Unit) {
    ListRow(null, title, note, first = first, onClick = onClick) {
        RowValue(value)
        RowChevron()
    }
}


