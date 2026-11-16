package com.wangzan101.mika.ui

import androidx.compose.runtime.remember

import com.wangzan101.mika.core.record.RunStats

import com.wangzan101.mika.core.record.RunMetricsStore

import androidx.compose.ui.platform.LocalContext

import androidx.compose.material3.TextButton

import com.wangzan101.mika.ui.theme.MikaTheme

import androidx.compose.material3.Text

import androidx.compose.material3.MaterialTheme

import androidx.compose.ui.unit.dp

import androidx.compose.foundation.layout.Spacer

import androidx.compose.foundation.layout.Arrangement

import androidx.compose.foundation.layout.padding

import androidx.compose.foundation.layout.fillMaxWidth

import androidx.compose.foundation.layout.Column

import com.wangzan101.mika.R
import com.wangzan101.mika.i18n.tr
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import com.wangzan101.mika.core.agent.SpeedFlags
import com.wangzan101.mika.core.agent.SpeedPreset
import com.wangzan101.mika.core.agent.SpeedPresets
import com.wangzan101.mika.ui.components.FooterNote
import com.wangzan101.mika.ui.components.GroupCard
import com.wangzan101.mika.ui.components.GroupLabel
import com.wangzan101.mika.ui.components.ListRow
import com.wangzan101.mika.ui.components.MikaSwitch
import com.wangzan101.mika.ui.components.PageScaffold
import com.wangzan101.mika.ui.components.RowChevron

/** 一个工程开关:[id] 用作测试标签,[change] 算出改过这一项之后的整组开关。 */
data class DevSwitch(
    val id: String, val title: String, val subtitle: String, val checked: Boolean, val change: (Boolean) -> SpeedFlags,
)

/** 开发者选项的两组:速度(已验证、默认多半开着)和实验(默认关)。开关的值与存储([SpeedFlags])不变。 */
object DeveloperSwitches {
    fun speed(flags: SpeedFlags): List<DevSwitch> = listOf(
        DevSwitch("adaptive-vision", tr(R.string.dev_adaptive), tr(R.string.dev_adaptive_sub), flags.adaptiveVision) { flags.copy(adaptiveVision = it) },
        DevSwitch("inline-screen", tr(R.string.dev_inline), tr(R.string.dev_inline_sub), flags.inlineScreen) { flags.copy(inlineScreen = it) },
        DevSwitch("batch-steps", tr(R.string.dev_batch), tr(R.string.dev_batch_sub), flags.batchSteps) { flags.copy(batchSteps = it) },
        DevSwitch("deep-links", tr(R.string.dev_deep_links), tr(R.string.dev_deep_links_sub), flags.deepLinks) { flags.copy(deepLinks = it) },
        DevSwitch("light-steps", tr(R.string.dev_light), tr(R.string.dev_light_sub), flags.lightSteps) { flags.copy(lightSteps = it) },
    )

    fun experimental(flags: SpeedFlags): List<DevSwitch> = listOf(
        DevSwitch("replay", tr(R.string.dev_replay), tr(R.string.dev_replay_sub), flags.replay) { flags.copy(replay = it) },
        DevSwitch("parallel-tasks", tr(R.string.dev_parallel), tr(R.string.dev_parallel_sub), flags.parallelTasks) { flags.copy(parallelTasks = it) },
        DevSwitch("structured-compaction", tr(R.string.dev_compaction), tr(R.string.dev_compaction_sub), flags.structuredCompaction) { flags.copy(structuredCompaction = it) },
        DevSwitch("tables-at-birth", tr(R.string.dev_screen_tables), tr(R.string.dev_screen_tables_sub), flags.tablesAtBirth) { flags.copy(tablesAtBirth = it) },
    )
}

/** 「做事方式」一组:任务运行页里的询问 / 自主全局开关。 */
object AutonomyCopy {
    val GROUP: String get() = tr(R.string.dev_group)
    val TITLE: String get() = tr(R.string.dev_autonomy)
    val SUBTITLE: String get() = tr(R.string.dev_autonomy_sub)
}

val DEVELOPER_NOTE: String get() = tr(R.string.dev_note)

/** 当前看图模型的「看图定位已验证」:[model] 是它的模型名。 */
data class GroundingSetting(val model: String, val verified: Boolean)

object GroundingCopy {
    val GROUP: String get() = tr(R.string.cap_vision)
    val TITLE: String get() = tr(R.string.dev_grounding)

    fun subtitle(model: String) = tr(R.string.dev_grounding_sub, model)
}

/**
 * 设置 › 高级与其他 › 开发者选项:最上面是「主动能力(实验)」的入口([onOpenProactive]);然后是速度和实验两组开关;
 * 有看图模型时另有它的「看图定位已验证」([grounding] 为 null 时不显示);最后是「运行统计」的入口([onOpenRunStats] 为 null 时不显示)。
 */
@Composable
fun DeveloperOptionsScreen(
    speed: SpeedFlags,
    onSpeed: (SpeedFlags) -> Unit,
    onBack: () -> Unit,
    grounding: GroundingSetting? = null,
    onGrounding: (Boolean) -> Unit = {},
    onOpenRunStats: (() -> Unit)? = null,
    onOpenProactive: (() -> Unit)? = null,
) {
    PageScaffold("进阶设置", onBack) {
        GroupCard {
            Column(Modifier.fillMaxWidth().padding(14.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text("排障用，平时不用动", style = MaterialTheme.typography.bodyMedium)
                Text("改动从下一次执行开始生效", style = MaterialTheme.typography.bodySmall,
                    color = MikaTheme.colors.ink3)
            }
        }
        if (onOpenProactive != null) {
            GroupCard {
                ListRow(null, tr(R.string.proactive_title), tr(R.string.proactive_entry_sub), first = true, onClick = onOpenProactive) { RowChevron() }
            }
        }
        // 三档预设:点一下把九个开关摆成常见取向,手动改过就显示「已自定义」
        val matched = SpeedPresets.detect(speed)
        GroupCard {
            SpeedPreset.entries.forEachIndexed { index, preset ->
                val title = when (preset) {
                    SpeedPreset.FAST -> "更快更省"
                    SpeedPreset.BALANCED -> "平衡（推荐）"
                    SpeedPreset.ACCURATE -> "更准更稳"
                }
                ListRow(null, title, if (matched == preset) "当前" else "", first = index == 0,
                    onClick = { onSpeed(SpeedPresets.flags(preset)) }) { RowChevron() }
            }
            if (matched == null) {
                FooterNote("已自定义 · 与「平衡」相差 " +
                    SpeedPresets.diffCount(speed, SpeedPreset.BALANCED) + " 项 · 点「平衡」可改回")
            }
        }
        GroupLabel(tr(R.string.dev_speed))
        SwitchGroup(DeveloperSwitches.speed(speed), onSpeed)
        GroupLabel(tr(R.string.dev_experiments))
        SwitchGroup(DeveloperSwitches.experimental(speed), onSpeed)
        if (grounding != null) {
        val anyExperimental = speed.replay || speed.parallelTasks || speed.structuredCompaction || speed.tablesAtBirth
        if (anyExperimental) {
            TextButton(onClick = {
                onSpeed(
                    SpeedFlags(
                        inlineScreen = speed.inlineScreen, batchSteps = speed.batchSteps,
                        deepLinks = speed.deepLinks, lightSteps = speed.lightSteps,
                        adaptiveVision = speed.adaptiveVision,
                    ),
                )
            }, modifier = Modifier.testTag("dev-experiments-off")) {
                Text("全部关实验")
            }
        }
            GroupLabel(GroundingCopy.GROUP)
            GroupCard {
                ListRow(null, GroundingCopy.TITLE, GroundingCopy.subtitle(grounding.model), first = true, onClick = { onGrounding(!grounding.verified) }) {
                    MikaSwitch(grounding.verified, onGrounding, Modifier.testTag("dev-grounding-verified"))
                }
            }
        }
        // 指标栏:直接读本机运行小结,没有数据就不显示
        val appCtx = LocalContext.current.applicationContext
        val recent = remember {
            runCatching {
                RunMetricsStore(java.io.File(appCtx.filesDir, RunMetricsStore.FILE_NAME)).recent(10)
            }.getOrDefault(emptyList())
        }
        if (recent.isNotEmpty()) {
            val stats = RunStats.of(recent)
            val calls = recent.sumOf { it.modelCalls }
            val perStep = if (calls > 0) stats.totalMs.toDouble() / calls / 1000.0 else 0.0
            GroupCard {
                ListRow(
                    null,
                    "最近 " + recent.size + " 次",
                    String.format("平均 %.1f 秒/步 · 成功 %d/%d", perStep, stats.succeeded, stats.runs),
                    first = true,
                ) { RowChevron() }
            }
        }
        GroupLabel(tr(R.string.dev_run_log))
        GroupCard {
            TraceSettingsRows()
            if (onOpenRunStats != null) {
                ListRow(null, RunMetricsCopy.STATS_TITLE, RunMetricsCopy.STATS_SUBTITLE, onClick = onOpenRunStats) { RowChevron() }
            }
        }
        FooterNote(DEVELOPER_NOTE)
    }
}

@Composable
private fun SwitchGroup(switches: List<DevSwitch>, onSpeed: (SpeedFlags) -> Unit) {
    GroupCard {
        switches.forEachIndexed { i, s ->
            // 整行都能点:开关小,行大
            ListRow(null, s.title, s.subtitle, first = i == 0, onClick = { onSpeed(s.change(!s.checked)) }) {
                MikaSwitch(s.checked, { onSpeed(s.change(it)) }, Modifier.testTag("dev-${s.id}"))
            }
        }
    }
}





