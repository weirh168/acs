package com.wangzan101.mika.core.agent

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SpeedPresetsTest {
    @Test fun eachPresetDetectsItself() {
        SpeedPreset.entries.forEach { preset ->
            assertEquals(0, SpeedPresets.diffCount(SpeedPresets.flags(preset), preset))
            assertEquals(preset, SpeedPresets.detect(SpeedPresets.flags(preset)))
        }
    }

    @Test fun balancedIsTheDefaultAndSitsBetweenTheOtherTwo() {
        // 平衡只开四项:比「更准更稳」多,比「更快更省」少
        assertTrue(SpeedPresets.diffCount(SpeedPresets.BALANCED, SpeedPreset.ACCURATE) > 0)
        assertTrue(SpeedPresets.diffCount(SpeedPresets.BALANCED, SpeedPreset.FAST) >
            SpeedPresets.diffCount(SpeedPresets.BALANCED, SpeedPreset.ACCURATE))
    }

    @Test fun oneManualChangeIsReportedAsCustomized() {
        val tuned = SpeedPresets.BALANCED.let { it.copyWith(deepLinks = true) }
        assertEquals(1, SpeedPresets.diffCount(tuned, SpeedPreset.BALANCED))
        assertNull(SpeedPresets.detect(tuned))
    }
}

/** 测试用的复制:只改一个开关。 */
private fun SpeedFlags.copyWith(
    inlineScreen: Boolean = this.inlineScreen,
    batchSteps: Boolean = this.batchSteps,
    replay: Boolean = this.replay,
    deepLinks: Boolean = this.deepLinks,
    lightSteps: Boolean = this.lightSteps,
    parallelTasks: Boolean = this.parallelTasks,
    structuredCompaction: Boolean = this.structuredCompaction,
    adaptiveVision: Boolean = this.adaptiveVision,
    tablesAtBirth: Boolean = this.tablesAtBirth,
) = SpeedFlags(
    inlineScreen = inlineScreen, batchSteps = batchSteps, replay = replay, deepLinks = deepLinks,
    lightSteps = lightSteps, parallelTasks = parallelTasks, structuredCompaction = structuredCompaction,
    adaptiveVision = adaptiveVision, tablesAtBirth = tablesAtBirth,
)
