package com.wangzan101.mika.core.agent

/**
 * 进阶设置的三档预设:把 9 个提速开关摆成三种常见取向。
 * 只做映射与差异计算,不碰存储 —— 存哪、什么时候写由 App 决定。
 */
enum class SpeedPreset { FAST, BALANCED, ACCURATE }

object SpeedPresets {
    /** 更快更省:全开,一切以省时省钱为先。 */
    val FAST = SpeedFlags(
        inlineScreen = true, batchSteps = true, replay = true, deepLinks = true,
        lightSteps = true, parallelTasks = true, structuredCompaction = true,
        adaptiveVision = true, tablesAtBirth = true,
    )

    /** 平衡(默认):只开"稳也不慢"的四项,其余关着。 */
    val BALANCED = SpeedFlags(
        adaptiveVision = true, batchSteps = true, inlineScreen = true, structuredCompaction = true,
    )

    /** 更准更稳:全关,每一步都看得清清楚楚。 */
    val ACCURATE = SpeedFlags.OFF

    fun flags(preset: SpeedPreset): SpeedFlags = when (preset) {
        SpeedPreset.FAST -> FAST
        SpeedPreset.BALANCED -> BALANCED
        SpeedPreset.ACCURATE -> ACCURATE
    }

    /** 当前开关与某个预设相差几项(0 表示完全一致,界面用它显示「已自定义・相差 N 项」)。 */
    fun diffCount(flags: SpeedFlags, preset: SpeedPreset): Int {
        val target = flags(preset)
        var diff = 0
        if (flags.inlineScreen != target.inlineScreen) diff++
        if (flags.batchSteps != target.batchSteps) diff++
        if (flags.replay != target.replay) diff++
        if (flags.deepLinks != target.deepLinks) diff++
        if (flags.lightSteps != target.lightSteps) diff++
        if (flags.parallelTasks != target.parallelTasks) diff++
        if (flags.structuredCompaction != target.structuredCompaction) diff++
        if (flags.adaptiveVision != target.adaptiveVision) diff++
        if (flags.tablesAtBirth != target.tablesAtBirth) diff++
        return diff
    }

    /** 完全等于某一档就返回它,否则 null(表示已自定义)。 */
    fun detect(flags: SpeedFlags): SpeedPreset? =
        SpeedPreset.entries.firstOrNull { diffCount(flags, it) == 0 }
}
