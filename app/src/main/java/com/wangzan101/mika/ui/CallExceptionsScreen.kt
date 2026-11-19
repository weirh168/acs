package com.wangzan101.mika.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.wangzan101.mika.calls.CallConfig
import com.wangzan101.mika.ui.theme.MikaTheme
import com.wangzan101.mika.ui.theme.MikaIcons
import com.wangzan101.mika.ui.components.*

/**
 * 例外名单:哪些号码「我自己接」、哪些「必须 AI 接」。
 * 原来这两组挂在接听页上各占一行、多半是 0 个,现在收进这一页,接听页只留一个入口。
 */
@Composable
internal fun CallExceptionsScreen(
    config: CallConfig,
    onSave: (CallConfig) -> Unit,
    onBack: () -> Unit,
) {
    var mine by rememberSaveable { mutableStateOf(true) }
    var adding by rememberSaveable { mutableStateOf("") }
    val current = if (mine) config.bypassIncomingNumbers else config.allowedIncomingNumbers

    fun add(number: String) {
        val parsed = parseCallNumberList(number)
        if (parsed.isNullOrEmpty() || incompleteCallNumbers(number).isNotEmpty()) return
        onSave(
            if (mine) config.copy(bypassIncomingNumbers = config.bypassIncomingNumbers + parsed)
            else config.copy(allowedIncomingNumbers = config.allowedIncomingNumbers + parsed),
        )
        adding = ""
    }

    fun remove(number: String) {
        onSave(
            if (mine) config.copy(bypassIncomingNumbers = config.bypassIncomingNumbers - number)
            else config.copy(allowedIncomingNumbers = config.allowedIncomingNumbers - number),
        )
    }

    PageScaffold("例外名单", onBack, Modifier.testTag("call-exceptions")) {
        Column(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            // 两段切换
            Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                SegmentButton("我自己接", mine, Modifier.weight(1f).testTag("exceptions-mine")) { mine = true }
                SegmentButton("必须 AI 接", !mine, Modifier.weight(1f).testTag("exceptions-ai")) { mine = false }
            }
            Text(
                if (mine) "这几个号码打来,AI 不会接,只响铃给你" else "这几个号码打来一律交给 AI,不管它在不在接听范围里",
                style = MaterialTheme.typography.bodySmall, color = MikaTheme.colors.ink3,
            )
            // 加号码
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = adding, onValueChange = { adding = it }, singleLine = true,
                    placeholder = { Text("加一个号码") },
                    modifier = Modifier.weight(1f).testTag("exceptions-input"),
                )
                CallPrimaryButton("加入", adding.isNotBlank(), { add(adding) }, Modifier.testTag("exceptions-add"))
            }
            GroupLabel(if (mine) "我自己接" else "必须 AI 接")
            if (current.isEmpty()) {
                GroupCard {
                    ListRow(MikaIcons.Phone, "还没有号码", "加上以后改完立即生效,不用重启", first = true) {}
                }
            } else {
                LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(current.toList()) { number ->
                        GroupCard {
                            ListRow(
                                MikaIcons.Phone, number,
                                if (mine) "打来只响铃,AI 不接" else "打来一律交给 AI",
                                first = true, onClick = { remove(number) },
                            ) { Text("移除", color = MikaTheme.colors.warn, style = MaterialTheme.typography.bodyMedium) }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SegmentButton(text: String, selected: Boolean, modifier: Modifier = Modifier, onClick: () -> Unit) {
    if (selected) {
        Button(onClick = onClick, modifier = modifier.heightIn(min = 44.dp)) {
            Text(text, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
    } else {
        OutlinedButton(onClick = onClick, modifier = modifier.heightIn(min = 44.dp)) {
            Text(text, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
    }
}