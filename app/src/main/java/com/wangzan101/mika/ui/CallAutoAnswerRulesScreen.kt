package com.wangzan101.mika.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
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
import android.content.Context
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.LaunchedEffect
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
import com.wangzan101.mika.calls.CallFallback
import androidx.compose.ui.platform.LocalContext
import androidx.compose.material3.Checkbox
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
    val allowPrefixes: Set<String>,
    val blockPrefixes: Set<String>,
    val activeStartMinute: Int,
    val activeEndMinute: Int,
    val fallback: CallFallback,
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
    /** 规则现在其实不会生效的原因(缺权限等);null 表示没问题。 */
    permissionIssue: String? = null,
    onFixPermissions: () -> Unit = {},
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
    var allowPrefixes by rememberSaveable { mutableStateOf(config.allowedPrefixes) }
    var blockPrefixes by rememberSaveable { mutableStateOf(config.blockedPrefixes) }
    var windowed by rememberSaveable { mutableStateOf(config.activeStartMinute >= 0 && config.activeEndMinute >= 0) }
    var startText by rememberSaveable { mutableStateOf<String>(CallTimeText.of(config.activeStartMinute)) }
    var endText by rememberSaveable { mutableStateOf<String>(CallTimeText.of(config.activeEndMinute)) }
    var fallback by rememberSaveable { mutableStateOf(config.fallback) }
    var delay by rememberSaveable { mutableStateOf(config.autoAnswerDelaySeconds) }
    var listsOpen by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf(false) }
    var notice by remember { mutableStateOf<String?>(null) }
    val importFailedText = stringResource(R.string.calls_rules_import_failed)
    val importedText = stringResource(R.string.calls_rules_imported)
    val scope = rememberCoroutineScope()

    val flags = listOf(contacts, strangers, hidden, spam, repeat, international)
    val startMinute = CallTimeText.parse(startText)
    val endMinute = CallTimeText.parse(endText)
    val windowValid = !windowed || (startMinute != null && endMinute != null)
    val dirty = preset != config.preset || !CallPresetDefaults.matches(preset, flags) ||
        allowed != config.allowedIncomingNumbers || blocked != config.blockedIncomingNumbers ||
        allowPrefixes != config.allowedPrefixes || blockPrefixes != config.blockedPrefixes ||
        windowed != (config.activeStartMinute >= 0) ||
        (windowed && (startMinute != config.activeStartMinute || endMinute != config.activeEndMinute)) ||
        fallback != config.fallback || delay != config.autoAnswerDelaySeconds
    val draft = CallRulesDraft(
        preset, contacts, strangers, hidden, spam, repeat, international, allowed, blocked,
        allowPrefixes, blockPrefixes,
        if (windowed) startMinute ?: -1 else -1,
        if (windowed) endMinute ?: -1 else -1,
        fallback, delay,
    )

    fun applyPreset(next: CallPreset) {
        preset = next
        val s = CallPresetDefaults.sources(next)
        contacts = s[0]; strangers = s[1]; hidden = s[2]; spam = s[3]; repeat = s[4]; international = s[5]
    }

    Dialog(onDismissRequest = { if (!busy) onDismiss() }, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(Modifier.fillMaxSize(), color = MikaTheme.colors.bg) {
            Box(Modifier.fillMaxSize()) {
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
                    if (permissionIssue != null) PermissionBanner(permissionIssue, onFixPermissions)
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
                    RulesPortSection(
                        export = { CallRulesJson.encode(draft) },
                        onImport = { text ->
                            val snap = CallRulesJson.decode(text)
                            if (snap == null) {
                                notice = importFailedText
                            } else {
                                preset = snap.preset; contacts = snap.answerContacts; strangers = snap.answerStrangers
                                hidden = snap.answerHidden; spam = snap.answerSpam; repeat = snap.answerRepeat
                                international = snap.answerInternational; blocked = snap.blocked
                                allowed = snap.allowed; allowPrefixes = snap.allowPrefixes
                                blockPrefixes = snap.blockPrefixes
                                windowed = snap.activeStartMinute >= 0 && snap.activeEndMinute >= 0
                                startText = CallTimeText.of(snap.activeStartMinute)
                                endText = CallTimeText.of(snap.activeEndMinute)
                                fallback = snap.fallback; delay = snap.delaySeconds
                                notice = importedText
                            }
                        },
                        onNotice = { notice = it },
                    )
                    Spacer(Modifier.size(14.dp))
                    WindowSection(windowed, startText, endText, windowValid,
                        onToggle = { windowed = it },
                        onStart = { startText = it }, onEnd = { endText = it })
                    Spacer(Modifier.size(14.dp))
                    FallbackSection(fallback) { fallback = it }
                    Spacer(Modifier.size(14.dp))
                    RingSection(delay) { delay = it }
                    Spacer(Modifier.size(20.dp))
                }
                Surface(color = MikaTheme.colors.surface, shadowElevation = 8.dp) {
                    Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(16.dp)) {
                        if (dirty) Text(stringResource(R.string.calls_unsaved), fontSize = 12.sp,
                            color = MikaTheme.colors.warn, modifier = Modifier.padding(bottom = 6.dp))
                        notice?.let { Text(it, fontSize = 12.sp, color = MikaTheme.colors.ok, modifier = Modifier.padding(bottom = 6.dp)) }
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
                // 名单/通讯录浮层:画在同一个 Dialog 里,不新开窗口
                if (listsOpen) {
                    CallNumbersOverlay(
                        allowed, blocked, allowPrefixes, blockPrefixes,
                        onDismiss = { listsOpen = false },
                    ) { a, b, ap, bp ->
                        allowed = a; blocked = b; allowPrefixes = ap; blockPrefixes = bp
                        listsOpen = false
                    }
                }
            }
        }
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
    // 按屏中心线平分:智能接听与全部交给 AI 各占一半宽度;只接名单单独一行铺满
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            PresetCard(stringResource(R.string.calls_preset_smart), stringResource(R.string.calls_preset_smart_note),
                selected = preset == CallPreset.SMART && !customized,
                badge = if (customized) stringResource(R.string.calls_preset_custom) else stringResource(R.string.calls_preset_recommended),
                tag = "call-preset-smart", modifier = Modifier.weight(1f).fillMaxHeight()) { onPick(CallPreset.SMART) }
            PresetCard(stringResource(R.string.calls_preset_all), stringResource(R.string.calls_preset_all_note),
                selected = preset == CallPreset.ALL, badge = null,
                tag = "call-preset-all", modifier = Modifier.weight(1f).fillMaxHeight()) { onPick(CallPreset.ALL) }
        }
        PresetCard(stringResource(R.string.calls_preset_list), stringResource(R.string.calls_preset_list_note),
            selected = preset == CallPreset.LIST, badge = null,
            tag = "call-preset-list", modifier = Modifier.fillMaxWidth()) { onPick(CallPreset.LIST) }
    }
}

@Composable
private fun PresetCard(title: String, note: String, selected: Boolean, badge: String?, tag: String,
                       modifier: Modifier = Modifier, onClick: () -> Unit) {
    val c = MikaTheme.colors
    Column(
        modifier.heightIn(min = 96.dp)
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

/**
 * 号码名单:白名单 / 黑名单,外加号段;支持从通讯录多选、粘贴批量。
 * 画成页面内的浮层而不是 AlertDialog —— 规则页本身已经是一个全屏 Dialog,
 * 再往里套系统对话框在部分机型上根本不会显示(之前「从通讯录选」点了没反应就是这个原因)。
 */
@Composable
private fun CallNumbersOverlay(
    allowed: Set<String>, blocked: Set<String>,
    allowPrefixes: Set<String>, blockPrefixes: Set<String>,
    onDismiss: () -> Unit,
    onApply: (Set<String>, Set<String>, Set<String>, Set<String>) -> Unit,
) {
    var allowMode by rememberSaveable { mutableStateOf(true) }
    var allowText by rememberSaveable { mutableStateOf(allowed.sorted().joinToString("\n")) }
    var blockText by rememberSaveable { mutableStateOf(blocked.sorted().joinToString("\n")) }
    var allowPrefixText by rememberSaveable { mutableStateOf(allowPrefixes.sorted().joinToString(",")) }
    var blockPrefixText by rememberSaveable { mutableStateOf(blockPrefixes.sorted().joinToString(",")) }
    var picking by remember { mutableStateOf(false) }
    val context = LocalContext.current
    val allowParsed = parseCallNumberList(allowText)
    val blockParsed = parseCallNumberList(blockText)
    val ok = allowParsed != null && blockParsed != null
    OverlayCard(onDismiss = onDismiss) {
        if (picking) {
            ContactsPanel(target = allowMode, onDismiss = { picking = false }) { numbers ->
                val merged = listOf(
                    if (allowMode) allowText else blockText,
                    numbers.joinToString("\n"),
                ).filter { it.isNotBlank() }.joinToString("\n")
                if (allowMode) allowText = merged else blockText = merged
                picking = false
            }
        } else {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(Modifier.fillMaxWidth().background(MikaTheme.colors.fill, RoundedCornerShape(10.dp)).padding(3.dp)) {
                    Segment(stringResource(R.string.calls_list_allow), allowMode) { allowMode = true }
                    Segment(stringResource(R.string.calls_list_block), !allowMode) { allowMode = false }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    ActionChip(stringResource(R.string.calls_list_import_contacts), "call-list-import") { picking = true }
                    ActionChip(stringResource(R.string.calls_list_paste), "call-list-paste") {
                        val clip = (context.getSystemService(Context.CLIPBOARD_SERVICE) as? android.content.ClipboardManager)
                            ?.primaryClip?.getItemAt(0)?.coerceToText(context)?.toString().orEmpty()
                        if (clip.isNotBlank()) {
                            if (allowMode) allowText = listOf(allowText, clip).filter { it.isNotBlank() }.joinToString("\n")
                            else blockText = listOf(blockText, clip).filter { it.isNotBlank() }.joinToString("\n")
                        }
                    }
                }
                OutlinedTextField(
                    if (allowMode) allowText else blockText,
                    { if (allowMode) allowText = it else blockText = it },
                    modifier = Modifier.fillMaxWidth().testTag(if (allowMode) "call-list-allow" else "call-list-block"),
                    label = { Text(stringResource(if (allowMode) R.string.calls_list_allow else R.string.calls_list_block)) },
                    supportingText = { Text(stringResource(if (allowMode) R.string.calls_list_allow_hint else R.string.calls_list_block_hint)) },
                    minLines = 3, maxLines = 6,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text),
                )
                OutlinedTextField(
                    if (allowMode) allowPrefixText else blockPrefixText,
                    { if (allowMode) allowPrefixText = it else blockPrefixText = it },
                    modifier = Modifier.fillMaxWidth().testTag("call-list-prefixes"),
                    label = { Text(stringResource(if (allowMode) R.string.calls_list_allow_prefix else R.string.calls_list_block_prefix)) },
                    supportingText = { Text(stringResource(R.string.calls_list_prefix_hint)) },
                    singleLine = true,
                )
                if (!ok) {
                    val bad = incompleteCallNumbers(if (allowMode) allowText else blockText)
                    Text(
                        if (bad.isNotEmpty()) stringResource(R.string.calls_list_incomplete, bad.joinToString("、"))
                        else stringResource(R.string.calls_allowlist_invalid, CallPolicy.MAX_ALLOWED_NUMBERS),
                        color = MaterialTheme.colorScheme.error, fontSize = 12.sp,
                    )
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    TextButton(onClick = onDismiss) { Text(stringResource(R.string.calls_cancel)) }
                    TextButton(enabled = ok, onClick = {
                        onApply(
                            allowParsed.orEmpty(), blockParsed.orEmpty(),
                            CallPrefixText.parse(allowPrefixText), CallPrefixText.parse(blockPrefixText),
                        )
                    }) { Text(stringResource(R.string.calls_save)) }
                }
            }
        }
    }
}

/** 页面内的浮层容器:半透明遮罩 + 卡片,不新开窗口,所以一定能显示出来。 */
@Composable
private fun OverlayCard(onDismiss: () -> Unit, content: @Composable () -> Unit) {
    Box(
        Modifier.fillMaxSize().background(androidx.compose.ui.graphics.Color.Black.copy(alpha = 0.55f))
            .clickable(indication = null, interactionSource = remember { androidx.compose.foundation.interaction.MutableInteractionSource() }) { onDismiss() },
        contentAlignment = Alignment.Center,
    ) {
        Surface(
            Modifier.fillMaxWidth().padding(16.dp).clickable(
                indication = null,
                interactionSource = remember { androidx.compose.foundation.interaction.MutableInteractionSource() },
            ) { },
            color = MikaTheme.colors.surface, shape = RoundedCornerShape(18.dp), shadowElevation = 12.dp,
        ) {
            Column(
                Modifier.heightIn(max = 620.dp).verticalScroll(rememberScrollState()).padding(16.dp),
            ) { content() }
        }
    }
}

/** 通讯录多选(同样是页面内浮层):勾中的号码回填到当前名单。 */
@Composable
private fun ContactsPanel(target: Boolean, onDismiss: () -> Unit, onPicked: (List<String>) -> Unit) {
    val context = LocalContext.current
    val contacts = remember { ContactsList.load(context) }
    var query by rememberSaveable { mutableStateOf("") }
    val picked = remember { mutableStateListOf<String>() }
    val shown = remember(query, contacts) {
        if (query.isBlank()) contacts else contacts.filter { it.second.contains(query) || it.first.contains(query, true) }
    }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.calls_list_import_contacts), fontSize = 17.sp,
                fontWeight = FontWeight.SemiBold, color = MikaTheme.colors.ink)
            Spacer(Modifier.weight(1f))
            Text(if (target) stringResource(R.string.calls_list_allow) else stringResource(R.string.calls_list_block),
                fontSize = 13.sp, color = MikaTheme.colors.ink3)
        }
        OutlinedTextField(query, { query = it }, modifier = Modifier.fillMaxWidth(),
            label = { Text(stringResource(R.string.calls_list_search)) }, singleLine = true)
        if (contacts.isEmpty()) {
            Text(stringResource(R.string.calls_list_no_contacts), fontSize = 13.sp, color = MikaTheme.colors.ink3)
        }
        Column(Modifier.heightIn(max = 280.dp).verticalScroll(rememberScrollState())) {
            shown.forEach { (name, number) ->
                val on = picked.contains(number)
                Row(Modifier.fillMaxWidth().toggleable(on, role = Role.Checkbox) {
                    if (it) picked.add(number) else picked.remove(number)
                }.heightIn(min = 44.dp), verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(on, null)
                    Column {
                        Text(name, fontSize = 15.sp, color = MikaTheme.colors.ink)
                        Text(number, fontSize = 13.sp, color = MikaTheme.colors.ink3)
                    }
                }
            }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
            TextButton(onClick = onDismiss) { Text(stringResource(R.string.calls_cancel)) }
            TextButton(enabled = picked.isNotEmpty(), onClick = { onPicked(picked.toList()) }) {
                Text(stringResource(R.string.calls_list_import_add, picked.size))
            }
        }
    }
}
@Composable
private fun ActionChip(text: String, tag: String, onClick: () -> Unit) {
    Box(
        Modifier.background(MikaTheme.colors.fill, RoundedCornerShape(10.dp)).clickable(onClick = onClick)
            .heightIn(min = 44.dp).padding(horizontal = 14.dp, vertical = 10.dp).testTag(tag),
    ) { Text(text, fontSize = 14.sp, color = MikaTheme.colors.ink) }
}

/** 只在通讯录读取权限在的时候查;读不到就当没有联系人。 */
internal object ContactsList {
    private const val MAX = 20_000

    /** 名单里的号码 -> 通讯录名字;查不到就不出现。 */
    fun namesFor(context: Context, numbers: Set<String>): List<String> = load(context)
        .filter { (_, number) -> numbers.any { expected ->
            com.wangzan101.mika.calls.CallPolicy.incomingMatchKey(expected) ==
                com.wangzan101.mika.calls.CallPolicy.incomingMatchKey(number)
        } }
        .map { it.second }.distinct()

    fun nameFor(context: Context, number: String): String? = load(context).firstOrNull { (_, candidate) ->
        com.wangzan101.mika.calls.CallPolicy.incomingMatchKey(candidate) ==
            com.wangzan101.mika.calls.CallPolicy.incomingMatchKey(number)
    }?.second

    fun load(context: Context): List<Pair<String, String>> {
        if (context.checkSelfPermission(android.Manifest.permission.READ_CONTACTS) !=
            android.content.pm.PackageManager.PERMISSION_GRANTED) return emptyList()
        return runCatching {
            context.contentResolver.query(
                android.provider.ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                arrayOf(android.provider.ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                    android.provider.ContactsContract.CommonDataKinds.Phone.NUMBER),
                null, null, null,
            )?.use { c ->
                // 号码一张表:姓名可以为空(只有号码的联系人也算),按纯数字去重
                val out = LinkedHashMap<String, Pair<String, String>>()
                val nameIdx = c.getColumnIndex(android.provider.ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
                val numberIdx = c.getColumnIndex(android.provider.ContactsContract.CommonDataKinds.Phone.NUMBER)
                while (c.moveToNext() && out.size < MAX) {
                    val number = c.getString(numberIdx)?.trim()?.takeIf { it.isNotBlank() } ?: continue
                    val name = c.getString(nameIdx)?.trim().orEmpty()
                    val key = number.filter { it.isDigit() }.ifBlank { number }
                    out.putIfAbsent(key, number to name)
                }
                out.values.toList()
            }.orEmpty()
        }.getOrDefault(emptyList())
    }
}

/** 号段输入:逗号/空格分开,归一到纯数字。 */
internal object CallPrefixText {
    fun parse(text: String): Set<String> =
        text.split(',', '，', ' ', '\n', ';', '；').mapNotNull(CallPolicy::normalisePrefix).toSet()
}

/** HH:MM 与分钟数互转;解析不出来返回 null。 */
internal object CallTimeText {
    fun of(minute: Int): String =
        if (minute !in 0..1439) "" else "%02d:%02d".format(minute / 60, minute % 60)

    fun parse(text: String): Int? {
        val m = Regex("^\\s*(\\d{1,2})\\s*[:：]\\s*(\\d{1,2})\\s*$").matchEntire(text) ?: return null
        val h = m.groupValues[1].toIntOrNull() ?: return null
        val mm = m.groupValues[2].toIntOrNull() ?: return null
        if (h !in 0..23 || mm !in 0..59) return null
        return h * 60 + mm
    }
}

/** 规则其实还没生效时(缺通话权限等)顶部的黄条。 */
@Composable
private fun PermissionBanner(text: String, onFix: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().padding(bottom = 12.dp)
            .background(MikaTheme.colors.warnSoft, RoundedCornerShape(12.dp)).padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(stringResource(R.string.calls_rules_blocked), fontSize = 14.sp,
                color = MikaTheme.colors.warn, fontWeight = FontWeight.SemiBold)
            Text(text, fontSize = 13.sp, color = MikaTheme.colors.ink2)
        }
        TextButton(onClick = onFix, modifier = Modifier.testTag("call-rules-fix")) {
            Text(stringResource(R.string.calls_rules_blocked_fix))
        }
    }
}

/** 规则导出/导入:一行 JSON 走剪贴板,方便在两台手机或重装后找回规则。 */
@Composable
private fun RulesPortSection(export: () -> String, onImport: (String) -> Unit, onNotice: (String?) -> Unit) {
    val context = LocalContext.current
    val copied = stringResource(R.string.calls_rules_exported)
    val empty = stringResource(R.string.calls_rules_import_empty)
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        ActionChip(stringResource(R.string.calls_rules_export), "call-rules-export") {
            val clip = context.getSystemService(Context.CLIPBOARD_SERVICE) as? android.content.ClipboardManager
            clip?.setPrimaryClip(android.content.ClipData.newPlainText("mika-call-rules", export()))
            onNotice(copied)
        }
        ActionChip(stringResource(R.string.calls_rules_import), "call-rules-import") {
            val text = (context.getSystemService(Context.CLIPBOARD_SERVICE) as? android.content.ClipboardManager)
                ?.primaryClip?.getItemAt(0)?.coerceToText(context)?.toString().orEmpty()
            if (text.isBlank()) onNotice(empty) else onImport(text)
        }
    }
}

/** 规则的 JSON 快照;只有规则本身,不含凭据、开场白这类别处也在用的设置。 */
internal data class RulesSnapshot(
    val preset: CallPreset,
    val answerContacts: Boolean, val answerStrangers: Boolean, val answerHidden: Boolean,
    val answerSpam: Boolean, val answerRepeat: Boolean, val answerInternational: Boolean,
    val allowed: Set<String>, val blocked: Set<String>,
    val allowPrefixes: Set<String>, val blockPrefixes: Set<String>,
    val activeStartMinute: Int, val activeEndMinute: Int,
    val fallback: CallFallback, val delaySeconds: Int,
)

internal object CallRulesJson {
    fun encode(draft: CallRulesDraft): String = org.json.JSONObject().apply {
        put("v", 1)
        put("preset", draft.preset.name)
        put("contacts", draft.answerContacts)
        put("strangers", draft.answerStrangers)
        put("hidden", draft.answerHidden)
        put("spam", draft.answerSpam)
        put("repeat", draft.answerRepeat)
        put("international", draft.answerInternational)
        put("allowed", org.json.JSONArray(draft.allowed.sorted()))
        put("blocked", org.json.JSONArray(draft.blocked.sorted()))
        put("allowPrefixes", org.json.JSONArray(draft.allowPrefixes.sorted()))
        put("blockPrefixes", org.json.JSONArray(draft.blockPrefixes.sorted()))
        put("windowStart", draft.activeStartMinute)
        put("windowEnd", draft.activeEndMinute)
        put("fallback", draft.fallback.name)
        put("delay", draft.delaySeconds)
    }.toString()

    fun decode(text: String): RulesSnapshot? = runCatching {
        val o = org.json.JSONObject(text.trim())
        fun strings(name: String): Set<String> {
            val a = o.optJSONArray(name) ?: return emptySet()
            return (0 until a.length()).mapNotNull { a.optString(it).takeIf { s -> s.isNotBlank() } }.toSet()
        }
        RulesSnapshot(
            preset = CallPreset.entries.firstOrNull { it.name == o.optString("preset") } ?: CallPreset.SMART,
            answerContacts = o.optBoolean("contacts", false),
            answerStrangers = o.optBoolean("strangers", true),
            answerHidden = o.optBoolean("hidden", false),
            answerSpam = o.optBoolean("spam", false),
            answerRepeat = o.optBoolean("repeat", true),
            answerInternational = o.optBoolean("international", false),
            allowed = strings("allowed"), blocked = strings("blocked"),
            allowPrefixes = strings("allowPrefixes"), blockPrefixes = strings("blockPrefixes"),
            activeStartMinute = o.optInt("windowStart", -1),
            activeEndMinute = o.optInt("windowEnd", -1),
            fallback = CallFallback.entries.firstOrNull { it.name == o.optString("fallback") } ?: CallFallback.WAIT_USER,
            delaySeconds = o.optInt("delay", CallConfig.MIN_AUTO_ANSWER_DELAY_SECONDS),
        )
    }.getOrNull()
}
/** 只在某段时间自动接。 */
@Composable
private fun WindowSection(
    windowed: Boolean, startText: String, endText: String, valid: Boolean,
    onToggle: (Boolean) -> Unit, onStart: (String) -> Unit, onEnd: (String) -> Unit,
) {
    val c = MikaTheme.colors
    Column(Modifier.fillMaxWidth().background(c.surface, RoundedCornerShape(14.dp)).padding(14.dp)) {
        Row(Modifier.fillMaxWidth().toggleable(windowed, role = Role.Switch) { onToggle(it) }
            .heightIn(min = 48.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(stringResource(R.string.calls_window_title), fontSize = 15.sp, color = c.ink)
                Text(stringResource(R.string.calls_window_note), fontSize = 13.sp, color = c.ink3)
            }
            Switch(windowed, null, modifier = Modifier.testTag("call-rules-window"))
        }
        if (windowed) {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(startText, onStart, modifier = Modifier.weight(1f).testTag("call-rules-window-start"),
                    label = { Text(stringResource(R.string.calls_window_from)) }, singleLine = true,
                    isError = !valid, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text))
                OutlinedTextField(endText, onEnd, modifier = Modifier.weight(1f).testTag("call-rules-window-end"),
                    label = { Text(stringResource(R.string.calls_window_to)) }, singleLine = true,
                    isError = !valid, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text))
            }
            Text(stringResource(R.string.calls_window_hint), fontSize = 12.sp, color = c.ink3)
        }
    }
}

/** AI 接不起来时怎么办。 */
@Composable
private fun FallbackSection(fallback: CallFallback, onChange: (CallFallback) -> Unit) {
    val c = MikaTheme.colors
    Column(Modifier.fillMaxWidth().background(c.surface, RoundedCornerShape(14.dp)).padding(14.dp)) {
        Text(stringResource(R.string.calls_fallback_title), fontSize = 15.sp, color = c.ink)
        Text(stringResource(R.string.calls_fallback_note), fontSize = 13.sp, color = c.ink3,
            modifier = Modifier.padding(top = 2.dp, bottom = 8.dp))
        Row(Modifier.fillMaxWidth().background(c.fill, RoundedCornerShape(10.dp)).padding(3.dp)) {
            Segment(stringResource(R.string.calls_fallback_wait), fallback == CallFallback.WAIT_USER) { onChange(CallFallback.WAIT_USER) }
            Segment(stringResource(R.string.calls_fallback_hangup), fallback == CallFallback.HANGUP) { onChange(CallFallback.HANGUP) }
        }
    }
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

















