package com.wangzan101.mika.ui

import androidx.compose.ui.platform.LocalContext

import androidx.compose.ui.text.font.FontWeight

import androidx.compose.ui.unit.sp

import android.net.Uri

import android.content.Intent

import androidx.compose.foundation.layout.RowScope

import androidx.compose.foundation.clickable

import androidx.compose.ui.graphics.Color

import androidx.compose.foundation.shape.RoundedCornerShape

import androidx.compose.foundation.background

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.listSaver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextDirection
import androidx.compose.ui.unit.dp
import com.wangzan101.mika.R
import com.wangzan101.mika.calls.CallActionResult
import com.wangzan101.mika.calls.CallConfig
import com.wangzan101.mika.calls.CallPolicy
import com.wangzan101.mika.calls.CallRuntimeState
import com.wangzan101.mika.calls.CallSim
import com.wangzan101.mika.calls.CallTaskBrief
import com.wangzan101.mika.ui.components.*
import com.wangzan101.mika.ui.theme.MikaIcons
import com.wangzan101.mika.ui.theme.MikaTheme

/** A private draft in the workspace, never a saved call profile or background request. */
@Stable
internal class CallTaskDraft {
    var number by mutableStateOf("")
    var goal by mutableStateOf("")
    var questions by mutableStateOf("")
    var context by mutableStateOf("")
    var constraints by mutableStateOf("")
    var simOverride by mutableStateOf<String?>(null)

    val hasContent: Boolean
        get() = number.isNotBlank() || goal.isNotBlank() || questions.isNotBlank() ||
            context.isNotBlank() || constraints.isNotBlank()

    fun fill(number: String, brief: CallTaskBrief) {
        this.number = number
        goal = brief.goal
        questions = brief.questions.joinToString("\n")
        context = brief.context
        constraints = brief.constraints
        simOverride = null
    }

    companion object {
        val Saver = listSaver<CallTaskDraft, String>(
            save = { draft -> listOf(draft.number, draft.goal, draft.questions, draft.context,
                draft.constraints, draft.simOverride.orEmpty()) },
            restore = { fields ->
                fields.takeIf { it.size == 6 }?.let {
                    CallTaskDraft().apply {
                        number = it[0]
                        goal = it[1]
                        questions = it[2]
                        context = it[3]
                        constraints = it[4]
                        simOverride = it[5].takeIf(String::isNotEmpty)
                    }
                }
            },
        )
    }
}

internal data class CallTaskSubmission(
    val number: String, val simId: String?, val simLabel: String, val voiceName: String, val brief: CallTaskBrief,
) {
    override fun toString(): String = "CallTaskSubmission(redacted)"
}

@Composable
internal fun CallTaskScreen(
    draft: CallTaskDraft, config: CallConfig, state: CallRuntimeState, ready: Boolean,
    editable: Boolean, canDial: Boolean, feedback: CallActionResult?,
    onSetup: () -> Unit, onConfirm: (CallTaskSubmission) -> Unit,
    onConfirmLocked: (CallTaskSubmission) -> Unit,
    voiceProfile: com.wangzan101.mika.calls.CallVoiceProfile,
    onVoiceProfiles: () -> Unit,
) {
    var questionsOpen by rememberSaveable { mutableStateOf(false) }
    var contextOpen by rememberSaveable { mutableStateOf(false) }
    var constraintsOpen by rememberSaveable { mutableStateOf(false) }
    var showSims by rememberSaveable { mutableStateOf(false) }
    var review by remember { mutableStateOf<CallTaskSubmission?>(null) }
    // 谁说话:AI 代拨 / 我自己拨。记住上次选择,但每次进入都在分段控件上明确显示
    var manual by rememberSaveable { mutableStateOf(false) }
    var transcribeAlso by rememberSaveable { mutableStateOf(false) }
    val number = CallPolicy.outgoingNumber(draft.number)
    val goalLength = draft.goal.trim().length
    val maxGoal = CallTaskBrief.MAX_GOAL_CHARS
    val questions = remember(draft.questions) { draft.questions.lineSequence().map(String::trim).filter(String::isNotEmpty).toList() }
    val badQuestions = questions.size > CallTaskBrief.MAX_QUESTIONS ||
        questions.any { it.length > CallTaskBrief.MAX_QUESTION_CHARS }
    val contextLength = draft.context.trim().length
    val constraintsLength = draft.constraints.trim().length
    val preferred = state.simOptions.firstOrNull { it.id == config.defaultOutgoingSimId }
    val sim = CallPolicy.chooseOutgoingSim(state.simOptions, draft.simOverride, config.defaultOutgoingSimId)
    val missingSim = stringResource(R.string.calls_task_pick_sim)
    val brief = remember(draft.goal, questions, draft.context, draft.constraints) {
        runCatching { CallTaskBrief(draft.goal, questions, draft.context, draft.constraints).validatedSnapshot() }.getOrNull()
    }

    CallDialModeSwitch(manual) { manual = it }
    if (manual) {
        CallManualDialBody(
            number = draft.number, onNumber = { draft.number = it }, editable = editable,
            parsed = number, simLabel = sim?.label ?: preferred?.label,
            sims = state.simOptions, chosenSim = draft.simOverride,
            defaultSimId = config.defaultOutgoingSimId,
            onSim = { draft.simOverride = it },
            transcribe = transcribeAlso, onTranscribe = { transcribeAlso = it },
        )
        return
    }

    feedback?.let { CallFeedback(it) }
    Column(Modifier.fillMaxWidth().testTag("call-task-fields"), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        OutlinedTextField(
            draft.number, { draft.number = it }, enabled = editable,
            label = { Text(stringResource(R.string.calls_number)) },
            modifier = Modifier.fillMaxWidth().testTag("call-number"), singleLine = true,
            textStyle = TextStyle(textDirection = TextDirection.Ltr),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
            isError = draft.number.isNotBlank() && number == null,
            supportingText = if (draft.number.isNotBlank() && number == null) ({
                Text(stringResource(R.string.calls_task_number_hint))
            }) else null,
        )
        OutlinedTextField(
            draft.goal, { draft.goal = it }, enabled = editable,
            label = { Text(stringResource(R.string.calls_task_goal)) },
            placeholder = { Text(stringResource(R.string.calls_task_goal_example)) },
            modifier = Modifier.fillMaxWidth().testTag("call-task-goal"), minLines = 2, maxLines = 3,
            isError = goalLength > maxGoal,
            supportingText = if (goalLength > maxGoal) ({
                Text(stringResource(R.string.calls_task_limit, goalLength, maxGoal))
            }) else null,
        )
    }
    Spacer(Modifier.height(8.dp))
    GroupCard {
        ListRow(MikaIcons.Mic, stringResource(R.string.calls_voice_service), voiceProfile.name, first = true,
            onClick = onVoiceProfiles.takeIf { editable }) { RowChevron() }
        HorizontalDivider()
        val simSummary = when {
            sim != null && draft.simOverride == null && sim.id == config.defaultOutgoingSimId ->
                stringResource(R.string.calls_sim_preferred, sim.label)
            sim != null && preferred != null && sim.id != preferred.id ->
                stringResource(R.string.calls_task_sim_override_summary, sim.label, preferred.label)
            sim != null -> sim.label
            config.defaultOutgoingSimId != null && draft.simOverride == null -> stringResource(R.string.calls_sim_unavailable)
            else -> missingSim
        }
        ListRow(MikaIcons.Phone, stringResource(R.string.calls_sim), simSummary,
            onClick = if (editable) ({ showSims = true }) else null) { RowChevron() }
    }

    GroupCard {
        CallFoldRow(MikaIcons.Doc, stringResource(R.string.calls_task_questions), questionsOpen, "call-task-questions-fold",
            subtitle = stringResource(if (draft.questions.isBlank()) R.string.calls_task_optional else R.string.calls_task_filled)) {
            questionsOpen = !questionsOpen
        }
        if (questionsOpen) OutlinedTextField(
            draft.questions, { draft.questions = it }, enabled = editable,
            label = { Text(stringResource(R.string.calls_task_questions)) },
            placeholder = { Text(stringResource(R.string.calls_task_questions_hint)) },
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp).padding(bottom = 8.dp).testTag("call-task-questions"),
            minLines = 2, maxLines = 4,
            isError = badQuestions,
            supportingText = if (badQuestions) ({
                Text(stringResource(R.string.calls_task_questions_limit, CallTaskBrief.MAX_QUESTIONS, CallTaskBrief.MAX_QUESTION_CHARS))
            }) else null,
        )
        HorizontalDivider()
        CallFoldRow(MikaIcons.Doc, stringResource(R.string.calls_task_context), contextOpen, "call-task-context-fold",
            subtitle = stringResource(if (draft.context.isBlank()) R.string.calls_task_optional else R.string.calls_task_filled)) {
            contextOpen = !contextOpen
        }
        if (contextOpen) CallTaskLongField(
            draft.context, { draft.context = it }, stringResource(R.string.calls_task_context),
            editable, contextLength, CallTaskBrief.MAX_CONTEXT_CHARS, "call-task-context",
        )
        HorizontalDivider()
        CallFoldRow(MikaIcons.Key, stringResource(R.string.calls_task_constraints), constraintsOpen, "call-task-constraints-fold",
            subtitle = stringResource(if (draft.constraints.isBlank()) R.string.calls_task_optional else R.string.calls_task_filled)) {
            constraintsOpen = !constraintsOpen
        }
        if (constraintsOpen) CallTaskLongField(
            draft.constraints, { draft.constraints = it }, stringResource(R.string.calls_task_constraints),
            editable, constraintsLength, CallTaskBrief.MAX_CONSTRAINT_CHARS, "call-task-constraints",
        )
    }

    if (!ready) {
        OutlinedButton(onClick = onSetup, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.calls_device_and_permissions))
        }
    }
    CallPrimaryButton(
        stringResource(R.string.calls_task_review), editable && number != null && brief != null,
        {
            if (number != null && brief != null) {
                review = CallTaskSubmission(number, sim?.id, sim?.label ?: missingSim, voiceProfile.name, brief)
            }
        },
        Modifier.testTag("call-task-review"),
    )
    Spacer(Modifier.height(8.dp))
    FooterNote(stringResource(R.string.calls_task_one_off))

    if (showSims) CallTaskSimDialog(
        state.simOptions, config.defaultOutgoingSimId, draft.simOverride,
        onChoose = { draft.simOverride = it; showSims = false }, onDismiss = { showSims = false },
    )
    review?.let { submission ->
        val allowed = ready && canDial && state.simOptions.any { it.id == submission.simId }
        CallTaskReviewDialog(
            submission, allowed,
            onDismiss = { review = null },
            onDial = { locked ->
                if (allowed) {
                    review = null
                    if (locked) onConfirmLocked(submission) else onConfirm(submission)
                }
            },
        )
    }
}

@Composable
private fun CallTaskLongField(
    value: String, onValue: (String) -> Unit, label: String, editable: Boolean, length: Int, max: Int, tag: String,
) {
    OutlinedTextField(
        value, onValue, enabled = editable, label = { Text(label) },
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp).padding(bottom = 8.dp).testTag(tag),
        minLines = 2, maxLines = 5, isError = length > max,
        supportingText = if (length > max) ({
            Text(stringResource(R.string.calls_task_limit, length, max))
        }) else null,
    )
}

@Composable
private fun CallTaskSimDialog(
    options: List<CallSim>, preferred: String?, selectedOverride: String?, onChoose: (String?) -> Unit, onDismiss: () -> Unit,
) {
    val remembered = options.firstOrNull { it.id == preferred }
    val platformDefault = options.singleOrNull { it.isDefault }
    AlertDialog(
        onDismissRequest = onDismiss, title = { Text(stringResource(R.string.calls_sim)) },
        text = {
            Column(Modifier.heightIn(max = 360.dp).verticalScroll(rememberScrollState())) {
                if (remembered != null) RadioRow(
                    stringResource(R.string.calls_sim_preferred, remembered.label), selectedOverride == null,
                    onClick = { onChoose(null) }, first = true,
                )
                if (platformDefault != null && options.size > 1) RadioRow(
                    stringResource(R.string.calls_default), selectedOverride == "default",
                    onClick = { onChoose("default") }, first = remembered == null, subtitle = platformDefault.label,
                )
                options.forEachIndexed { index, option ->
                    RadioRow(option.label, selectedOverride == option.id, onClick = { onChoose(option.id) },
                        first = index == 0 && remembered == null && platformDefault == null)
                }
                if (options.isEmpty()) Text(stringResource(R.string.calls_task_pick_sim))
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.calls_cancel)) } },
    )
}

@Composable
private fun CallTaskReviewDialog(submission: CallTaskSubmission, canDial: Boolean, onDismiss: () -> Unit, onDial: (Boolean) -> Unit) {
    var locked by remember { mutableStateOf(false) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.calls_task_review)) },
        modifier = Modifier.testTag("call-task-review-dialog"),
        text = {
            Column(Modifier.heightIn(max = 400.dp).verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(9.dp)) {
                TaskReviewField(stringResource(R.string.calls_number), "\u2066${submission.number}\u2069")
                TaskReviewField(stringResource(R.string.calls_sim), submission.simLabel)
                TaskReviewField(stringResource(R.string.calls_voice_service), submission.voiceName)
                TaskReviewField(stringResource(R.string.calls_task_goal), submission.brief.goal)
                if (submission.brief.questions.isNotEmpty()) {
                    TaskReviewField(stringResource(R.string.calls_task_questions),
                        submission.brief.questions.mapIndexed { index, question -> "${index + 1}. $question" }.joinToString("\n"))
                }
                if (submission.brief.context.isNotBlank()) TaskReviewField(stringResource(R.string.calls_task_context), submission.brief.context)
                if (submission.brief.constraints.isNotBlank()) TaskReviewField(stringResource(R.string.calls_task_constraints), submission.brief.constraints)
                if (canDial) {
                    for (mode in listOf(false, true)) {
                        Row(Modifier.fillMaxWidth().heightIn(min = 48.dp)
                            .testTag(if (mode) "call-mode-lock" else "call-mode-now")
                            .selectable(selected = locked == mode, role = Role.RadioButton) { locked = mode },
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            RadioButton(selected = locked == mode, onClick = null)
                            Text(stringResource(if (mode) R.string.calls_task_dial_locked else R.string.calls_task_dial_now))
                        }
                    }
                }
                Text(stringResource(when {
                    !canDial -> R.string.calls_task_review_blocked
                    locked -> R.string.calls_task_dial_locked_note
                    else -> R.string.calls_task_confirm_note
                }),
                    style = MaterialTheme.typography.bodySmall, color = MikaTheme.colors.ink3)
            }
        },
        confirmButton = {
            TextButton(onClick = { onDial(locked) }, enabled = canDial,
                modifier = Modifier.testTag(if (locked) "call-dial-locked" else "call-dial")) {
                Text(stringResource(if (locked) R.string.calls_task_dial_locked_confirm else R.string.calls_task_confirm_dial))
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, modifier = Modifier.testTag("call-task-review-cancel")) {
                Text(stringResource(R.string.calls_task_back_to_edit))
            }
        },
    )
}

@Composable
private fun TaskReviewField(label: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = MikaTheme.colors.ink3)
        Text(value, style = MaterialTheme.typography.bodyMedium)
    }
}

/** AI 代拨 / 我自己拨:这是「谁说话」的决策,所以放最上面。 */
@Composable
private fun CallDialModeSwitch(manual: Boolean, onChange: (Boolean) -> Unit) {
    Row(
        Modifier.fillMaxWidth().background(MikaTheme.colors.fill, RoundedCornerShape(14.dp))
            .padding(4.dp).testTag("call-dial-mode"),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        ModeHalf(stringResource(R.string.calls_mode_ai), !manual, "call-mode-ai") { onChange(false) }
        ModeHalf(stringResource(R.string.calls_mode_manual), manual, "call-mode-manual") { onChange(true) }
    }
}

@Composable
private fun RowScope.ModeHalf(text: String, selected: Boolean, tag: String, onClick: () -> Unit) {
    Box(
        Modifier.weight(1f).heightIn(min = 44.dp)
            .background(if (selected) MikaTheme.colors.surface else Color.Transparent, RoundedCornerShape(11.dp))
            .clickable(onClick = onClick).testTag(tag),
        contentAlignment = Alignment.Center,
    ) {
        Text(text, fontSize = 15.sp,
            color = if (selected) MikaTheme.colors.ink else MikaTheme.colors.ink3,
            fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal)
    }
}

/**
 * 我自己拨:只有号码、拨出卡、要不要事后转文字。
 * 这里用的是系统拨号,AI 全程不参与 —— 不连接实时语音、不播开场白。
 */
@Composable
private fun CallManualDialBody(
    number: String, onNumber: (String) -> Unit, editable: Boolean, parsed: String?,
    simLabel: String?, sims: List<CallSim>, chosenSim: String?, defaultSimId: String?,
    onSim: (String?) -> Unit,
    transcribe: Boolean, onTranscribe: (Boolean) -> Unit,
) {
    val context = LocalContext.current
    Column(Modifier.fillMaxWidth().testTag("call-manual-body"), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        OutlinedTextField(
            number, onNumber, enabled = editable,
            label = { Text(stringResource(R.string.calls_number)) },
            modifier = Modifier.fillMaxWidth().testTag("call-number"),
            singleLine = true,
            textStyle = TextStyle(textDirection = TextDirection.Ltr),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
            isError = number.isNotBlank() && parsed == null,
        )
        GroupCard {
            Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(stringResource(R.string.calls_outgoing_sim), fontSize = 15.sp, color = MikaTheme.colors.ink)
                Spacer(Modifier.weight(1f))
                Text(simLabel ?: stringResource(R.string.calls_task_pick_sim), fontSize = 14.sp,
                    color = MikaTheme.colors.ink3)
            }
        }
        GroupCard {
            Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(stringResource(R.string.calls_manual_transcribe), fontSize = 15.sp, color = MikaTheme.colors.ink)
                    Text(
                        stringResource(
                            if (android.os.Build.VERSION.SDK_INT >= 29) R.string.calls_manual_transcribe_blocked
                            else R.string.calls_manual_transcribe_note,
                        ),
                        fontSize = 13.sp, color = MikaTheme.colors.ink3,
                    )
                }
                Switch(transcribe, { onTranscribe(it) }, enabled = false, modifier = Modifier.testTag("call-manual-transcribe"))
            }
        }
        FooterNote(stringResource(R.string.calls_manual_note))
        Spacer(Modifier.size(8.dp))
        CallPrimaryButton(stringResource(R.string.calls_manual_dial), parsed != null && editable, {
            val target = parsed
            if (target == null) return@CallPrimaryButton
            val canCall = context.checkSelfPermission(android.Manifest.permission.CALL_PHONE) ==
                android.content.pm.PackageManager.PERMISSION_GRANTED
            val uri = Uri.fromParts("tel", target, null)
            val wantedSim = chosenSim ?: sims.firstOrNull { it.isDefault }?.id ?: defaultSimId
            val telecom = context.getSystemService(android.telecom.TelecomManager::class.java)
            // 有拨号权限就自己拨,并**沿用同一张卡**,避免 AI 用卡 1、人工用卡 2 的资费意外
            val placed = if (canCall && telecom != null) {
                runCatching {
                    val handle = telecom.callCapablePhoneAccounts.firstOrNull { wantedSim == null || it.id == wantedSim }
                    if (handle == null) false else {
                        val extras = android.os.Bundle().apply {
                            putParcelable(android.telecom.TelecomManager.EXTRA_PHONE_ACCOUNT_HANDLE, handle)
                        }
                        telecom.placeCall(uri, extras)
                        true
                    }
                }.getOrDefault(false)
            } else false
            if (!placed) {
                // 退回系统:有权限用 ACTION_CALL,没有就用拨号盘(号码已填好,按一下即可)
                val call = Intent(if (canCall) Intent.ACTION_CALL else Intent.ACTION_DIAL, uri)
                call.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                runCatching { context.startActivity(call) }
            }
        }, Modifier.fillMaxWidth().testTag("call-manual-dial"))
        if (parsed == null) FooterNote(stringResource(R.string.calls_manual_need_number))
    }
}





