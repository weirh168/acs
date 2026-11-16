package com.wangzan101.mika.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.wangzan101.mika.R
import com.wangzan101.mika.calls.CallConfig
import com.wangzan101.mika.calls.CallPolicy
import com.wangzan101.mika.calls.CallPreset
import com.wangzan101.mika.ui.components.GroupCard
import com.wangzan101.mika.ui.theme.MikaIcons
import com.wangzan101.mika.ui.theme.MikaTheme
import kotlinx.coroutines.launch

/** 保存一条规则时提交的东西:预设、六个来源开关、白/黑名单、响铃秒数。 */
data class CallRulesDraft(
    val preset: CallPreset,
    val answerContacts: Boolean,
    val answerStrangers: Boolean,
    val answerHidden: Boolean,
    val answerSpam: Boolean,
    val answerRepeat: Boolean,
    val answerInternational: Boolean,
    val allowed: Set<String>,
    val blocked: Set<String>,
    val delaySeconds: Int,
)

/** 预设卡的规范开关组合:点了卡片就按这套摆,手动改开关就变成「已自定义」。 */
internal object CallPresetDefaults {
    fun sources(preset: CallPreset): List<Boolean> = when (preset) {
        // 智能接听:通讯录你接,陌生号码和重复来电交给 AI,隐藏/国际/骚扰不接
        CallPreset.SMART -> listOf(false, true, false, false, true, false)
        // 全部交给 AI:六个来源全接
        CallPreset.ALL -> listOf(true, true, true, true, true, true)
        // 只接名单:来源开关此时不起作用,保持关掉,避免看起来像是开着
        CallPreset.LIST -> listOf(false, false, false, false, false, false)
    }

    fun matches(preset: CallPreset, flags: List<Boolean>): Boolean = sources(preset) == flags
}

/**
 * 自动接听规则:一张页面把「预设 → 来源开关 → 名单/响铃」按三层摆开,
 * 顶部一句话说清现在会发生什么。改动先留在本地,点「保存并生效」才写进设置。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CallAutoAnswerRulesDialog(
    config: CallConfig,
    onDismiss: () -> Unit,
    onSave: suspend (CallRulesDraft) -> Boolean,
) {
    var preset by rememberSaveable { mutableStateOf(config.preset) }
    var contacts by rememberSaveable { mutableStateOf(config.answerContacts) }
    var strangers by rememberSaveable { mutableStateOf(config.answerStrangers) }
    var hidden by rememberSaveable { mutableStateOf(config.answerHidden) }
    var spam by rememberSaveable { mutableStateOf(config.answerSpam) }
    var repeat by rememberSaveable { mutableStateOf(config.answerRepeat) }
    var international by rememberSaveable { mutableStateOf(config.answerInternational) }
    var allowed by rememberSaveable { mutableStateOf(config.allowedIncomingNumbers) }
    var blocked by rememberSaveable { mutableStateOf(config.blockedIncomingNumbers) }
    var delay by rememberSaveable { mutableStateOf(config.autoAnswerDelaySeconds) }
    var listsOpen by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    val flags = listOf(contacts, strangers, hidden, spam, repeat, international)
    val dirty = preset != config.preset || !CallPresetDefaults.matches(preset, flags) ||
        allowed != config.allowedIncomingNumbers || blocked != config.blockedIncomingNumbers ||
        delay != config.autoAnswerDelaySeconds
    val draft = CallRulesDraft(preset, contacts, strangers, hidden, spam, repeat, international, allowed, blocked, delay)

    fun applyPreset(next: CallPreset) {
        preset = next
        val s = CallPresetDefaults.sources(next)
        contacts = s[0]; strangers = s[1]; hidden = s[2]; spam = s[3]; repeat = s[4]; international = s[5]
    }

    Dialog(onDismissRequest = { if (!busy) onDismiss() }, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(Modifier.fillMaxSize(), color = MikaTheme.colors.bg) {
            Column(Modifier.fillMaxSize().statusBarsPadding()) {
                Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp)) {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        TextButton(onClick = { if (!busy) onDismiss() }, enabled = !busy,
                            modifier = Modifier.testTag("call-rules-close")) { Text(stringResource(R.string.calls_cancel)) }
                        Spacer(Modifier.weight(1f))
                    }
                    Text(stringResource(R.string.calls_rules), fontSize = 22.sp, fontWeight = FontWeight.SemiBold,
                        color = MikaTheme.colors.ink, modifier = Modifier.padding(bottom = 2.dp))
                    Text(stringResource(R.string.calls_rules_intro), fontSize = 13.sp,
                        color = MikaTheme.colors.ink3, modifier = Modifier.padding(bottom = 12.dp))
                }
                Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp)) {
                    SummaryCard(draft)
                    Spacer(Modifier.size(14.dp))
                    PresetCards(preset, flags, ::applyPreset)
                    Spacer(Modifier.size(16.dp))
                    SectionTitle(stringResource(R.string.calls_sources_title))
                    GroupCard {
                        SourceRow(stringResource(R.string.calls_source_contacts), contacts, true) { contacts = it; preset = keep(preset) }
                        SourceRow(stringResource(R.string.calls_source_strangers), strangers) { strangers = it }
                        SourceRow(stringResource(R.string.calls_source_hidden), hidden) { hidden = it }
                        SourceRow(stringResource(R.string.calls_source_spam), spam, subtitle = stringResource(R.string.calls_source_spam_note), enabled = false) {}
                        SourceRow(stringResource(R.string.calls_source_repeat), repeat,
                            subtitle = stringResource(R.string.calls_source_repeat_note)) { repeat = it }
                        SourceRow(stringResource(R.string.calls_source_international), international) { international = it }
                    }
                    Spacer(Modifier.size(14.dp))
                    GroupCard {
                        Row(Modifier.fillMaxWidth().clickable { listsOpen = true }
                            .heightIn(min = 52.dp).padding(horizontal = 16.dp),
                            verticalAlignment = Alignment.CenterVertically) {
                            Text(stringResource(R.string.calls_numbers_title), fontSize = 15.sp, color = MikaTheme.colors.ink)
                            Spacer(Modifier.weight(1f))
                            Text(
                                stringResource(R.string.calls_numbers_count, allowed.size + blocked.size),
                                fontSize = 14.sp, color = MikaTheme.colors.ink3,
                            )
                            Spacer(Modifier.size(6.dp))
                            androidx.compose.material3.Icon(MikaIcons.Chevron, null, tint = MikaTheme.colors.ink3,
                                modifier = Modifier.size(18.dp))
                        }
                    }
                    Spacer(Modifier.size(14.dp))
                    RingSection(delay) { delay = it }
                    Spacer(Modifier.size(20.dp))
                }
                Surface(color = MikaTheme.colors.surface, shadowElevation = 8.dp) {
                    Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(16.dp)) {
                        if (dirty) Text(stringResource(R.string.calls_unsaved), fontSize = 12.sp,
                            color = MikaTheme.colors.warn, modifier = Modifier.padding(bottom = 6.dp))
                        if (error) Text(stringResource(R.string.calls_action_failed), fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(bottom = 6.dp))
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            TextButton(onClick = {
                                applyPreset(CallPreset.SMART)
                                allowed = emptySet(); blocked = emptySet()
                                delay = CallConfig.MIN_AUTO_ANSWER_DELAY_SECONDS
                            }, enabled = !busy, modifier = Modifier.testTag("call-rules-reset")) {
                                Text(stringResource(R.string.calls_reset_default), fontSize = 14.sp)
                            }
                            CallPrimaryButton(stringResource(R.string.calls_save_apply), !busy, {
                                busy = true
                                scope.launch {
                                    try {
                                        if (onSave(draft)) onDismiss() else error = true
                                    } finally { busy = false }
                                }
                            }, Modifier.weight(1f).testTag("call-rules-save"))
                        }
                    }
                }
            }
        }
    }

    if (listsOpen) {
        CallNumbersDialog(allowed, blocked, onDismiss = { listsOpen = false }) { a, b ->
            allowed = a; blocked = b; listsOpen = false
        }
    }
}

private fun keep(preset: CallPreset): CallPreset = preset

@Composable
private fun SummaryCard(draft: CallRulesDraft) {
    val ai = mutableListOf<String>()
    val me = mutableListOf<String>()
    if (draft.preset == CallPreset.ALL) {
        ai += stringResource(R.string.calls_summary_everyone)
    } else if (draft.preset == CallPreset.LIST) {
        me += stringResource(R.string.calls_summary_not_in_list)
    } else {
        fun put(on: Boolean, label: String) { if (on) ai += label else me += label }
        put(draft.answerContacts, stringResource(R.string.calls_source_contacts))
        put(draft.answerStrangers, stringResource(R.string.calls_source_strangers))
        put(draft.answerHidden, stringResource(R.string.calls_source_hidden))
        put(draft.answerRepeat, stringResource(R.string.calls_source_repeat))
        put(draft.answerInternational, stringResource(R.string.calls_source_international))
    }
    Column(Modifier.fillMaxWidth().background(MikaTheme.colors.accentSoft, RoundedCornerShape(14.dp))
        .padding(14.dp).testTag("call-rules-summary")) {
        if (ai.isNotEmpty()) {
            Text(stringResource(R.string.calls_summary_ai, ai.joinToString("、")), fontSize = 15.sp,
                lineHeight = 21.sp, color = MikaTheme.colors.ink)
        }
        if (me.isNotEmpty()) {
            Text(stringResource(R.string.calls_summary_me, me.joinToString("、")), fontSize = 15.sp,
                lineHeight = 21.sp, color = MikaTheme.colors.ink)
        }
        Text(stringResource(R.string.calls_summary_ring, draft.delaySeconds), fontSize = 13.sp,
            color = MikaTheme.colors.ink2, modifier = Modifier.padding(top = 4.dp))
    }
}

@Composable
private fun PresetCards(preset: CallPreset, flags: List<Boolean>, onPick: (CallPreset) -> Unit) {
    val customized = preset == CallPreset.SMART && !CallPresetDefaults.matches(CallPreset.SMART, flags)
    Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        PresetCard(stringResource(R.string.calls_preset_smart), stringResource(R.string.calls_preset_smart_note),
            selected = preset == CallPreset.SMART && !customized,
            badge = if (customized) stringResource(R.string.calls_preset_custom) else stringResource(R.string.calls_preset_recommended),
            tag = "call-preset-smart") { onPick(CallPreset.SMART) }
        PresetCard(stringResource(R.string.calls_preset_all), stringResource(R.string.calls_preset_all_note),
            selected = preset == CallPreset.ALL, badge = null, tag = "call-preset-all") { onPick(CallPreset.ALL) }
        PresetCard(stringResource(R.string.calls_preset_list), stringResource(R.string.calls_preset_list_note),
            selected = preset == CallPreset.LIST, badge = null, tag = "call-preset-list") { onPick(CallPreset.LIST) }
    }
}

@Composable
private fun PresetCard(title: String, note: String, selected: Boolean, badge: String?, tag: String, onClick: () -> Unit) {
    val c = MikaTheme.colors
    Column(
        Modifier.width(190.dp).heightIn(min = 96.dp)
            .background(if (selected) c.accentSoft else c.surface, RoundedCornerShape(14.dp))
            .border(if (selected) 1.5.dp else 1.dp, if (selected) c.accent else c.edge, RoundedCornerShape(14.dp))
            .clickable(onClick = onClick).padding(12.dp).testTag(tag),
    ) {
        if (badge != null) Text(badge, fontSize = 11.sp, color = if (selected) c.accent else c.ink3,
            fontWeight = FontWeight.Medium)
        Text(title, fontSize = 16.sp, fontWeight = FontWeight.SemiBold, color = c.ink)
        Text(note, fontSize = 13.sp, lineHeight = 18.sp, color = c.ink2, modifier = Modifier.padding(top = 2.dp))
    }
}

@Composable
private fun SourceRow(title: String, on: Boolean, first: Boolean = false, subtitle: String? = null,
                      enabled: Boolean = true, onChange: (Boolean) -> Unit) {
    val c = MikaTheme.colors
    Column {
        if (!first) Box(Modifier.fillMaxWidth().padding(start = 16.dp).size(1.dp)
            .background(c.hair))
        Row(Modifier.fillMaxWidth().toggleable(on, enabled = enabled, role = Role.Switch) { onChange(it) }
            .heightIn(min = 52.dp).padding(horizontal = 16.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(title, fontSize = 15.sp, color = if (enabled) c.ink else c.ink3)
                if (subtitle != null) Text(subtitle, fontSize = 13.sp, color = c.ink3, lineHeight = 18.sp)
            }
            Switch(on, null, enabled = enabled, modifier = Modifier.testTag("call-source-" + title.hashCode()))
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RingSection(seconds: Int, onChange: (Int) -> Unit) {
    val c = MikaTheme.colors
    Column(Modifier.fillMaxWidth().background(c.surface, RoundedCornerShape(14.dp)).padding(14.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.calls_ring_title), fontSize = 15.sp, color = c.ink)
            Spacer(Modifier.weight(1f))
            Text(stringResource(R.string.calls_ring_value, seconds), fontSize = 15.sp,
                fontWeight = FontWeight.SemiBold, color = c.accent)
        }
        Slider(
            value = seconds.toFloat(),
            onValueChange = { onChange(it.toInt()) },
            valueRange = CallConfig.MIN_AUTO_ANSWER_DELAY_SECONDS.toFloat()..CallConfig.MAX_AUTO_ANSWER_DELAY_SECONDS.toFloat(),
            steps = CallConfig.MAX_AUTO_ANSWER_DELAY_SECONDS - CallConfig.MIN_AUTO_ANSWER_DELAY_SECONDS - 1,
            modifier = Modifier.fillMaxWidth().padding(top = 4.dp).testTag("call-rules-delay"),
        )
        Row(Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.calls_ring_soon), fontSize = 12.sp, color = c.ink3)
            Spacer(Modifier.weight(1f))
            Text(stringResource(R.string.calls_ring_two), fontSize = 12.sp, color = c.ink3)
            Spacer(Modifier.weight(1f))
            Text(stringResource(R.string.calls_ring_later), fontSize = 12.sp, color = c.ink3)
        }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(text, fontSize = 13.sp, fontWeight = FontWeight.Medium, color = MikaTheme.colors.ink2,
        modifier = Modifier.padding(start = 4.dp, bottom = 6.dp))
}

/** 白名单 / 黑名单:一个分段控件加一个多行输入框,保存时统一归一化。 */
@Composable
private fun CallNumbersDialog(
    allowed: Set<String>, blocked: Set<String>, onDismiss: () -> Unit,
    onApply: (Set<String>, Set<String>) -> Unit,
) {
    var allowMode by rememberSaveable { mutableStateOf(true) }
    var allowText by rememberSaveable { mutableStateOf(allowed.sorted().joinToString("\n")) }
    var blockText by rememberSaveable { mutableStateOf(blocked.sorted().joinToString("\n")) }
    val allowParsed = parseCallNumberList(allowText)
    val blockParsed = parseCallNumberList(blockText)
    val ok = allowParsed != null && blockParsed != null
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.calls_numbers_title)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(Modifier.fillMaxWidth().background(MikaTheme.colors.fill, RoundedCornerShape(10.dp)).padding(3.dp)) {
                    Segment(stringResource(R.string.calls_list_allow), allowMode) { allowMode = true }
                    Segment(stringResource(R.string.calls_list_block), !allowMode) { allowMode = false }
                }
                OutlinedTextField(
                    if (allowMode) allowText else blockText,
                    { if (allowMode) allowText = it else blockText = it },
                    modifier = Modifier.fillMaxWidth().testTag(if (allowMode) "call-list-allow" else "call-list-block"),
                    label = { Text(stringResource(if (allowMode) R.string.calls_list_allow else R.string.calls_list_block)) },
                    supportingText = { Text(stringResource(if (allowMode) R.string.calls_list_allow_hint else R.string.calls_list_block_hint)) },
                    minLines = 4, maxLines = 8,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text),
                )
                if (!ok) Text(stringResource(R.string.calls_allowlist_invalid, CallPolicy.MAX_ALLOWED_NUMBERS),
                    color = MaterialTheme.colorScheme.error, fontSize = 12.sp)
            }
        },
        confirmButton = {
            TextButton(enabled = ok, onClick = {
                onApply(allowParsed.orEmpty(), blockParsed.orEmpty())
            }) { Text(stringResource(R.string.calls_save)) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.calls_cancel)) } },
    )
}

@Composable
private fun androidx.compose.foundation.layout.RowScope.Segment(text: String, selected: Boolean, onClick: () -> Unit) {
    Box(Modifier.weight(1f).heightIn(min = 40.dp)
        .background(if (selected) MikaTheme.colors.surface else androidx.compose.ui.graphics.Color.Transparent,
            RoundedCornerShape(8.dp))
        .clickable(onClick = onClick), contentAlignment = Alignment.Center) {
        Text(text, fontSize = 14.sp, textAlign = TextAlign.Center,
            color = if (selected) MikaTheme.colors.ink else MikaTheme.colors.ink3,
            fontWeight = if (selected) FontWeight.Medium else FontWeight.Normal)
    }
}



