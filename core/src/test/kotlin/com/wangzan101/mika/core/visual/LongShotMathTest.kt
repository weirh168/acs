package com.wangzan101.mika.core.visual

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** 长截图对齐与规划的纯逻辑测试(不需要 Android)。 */
class LongShotMathTest {

    private val width = 108
    private val height = 400

    /** 造一屏:每一行一个稳定的颜色,第 [offset] 行开始是内容;上下各留一点"钉住的栏"。 */
    private fun screen(offset: Int, chrome: Boolean = true): IntArray {
        val px = IntArray(width * height)
        for (y in 0 until height) {
            val contentY = y + offset
            // 内容:按行号取伪随机色,保证不同行不同色、同一行稳定,且没有周期性(否则会对到别的位置)
            var h = contentY * 2654435761L
            h = h xor (h shr 13)
            h *= 0x5bd1e995L
            h = h xor (h shr 15)
            val color = 0xFF000000.toInt() or ((h and 0xFF).toInt() shl 16) or (((h shr 8) and 0xFF).toInt() shl 8) or ((h shr 16) and 0xFF).toInt()
            px.fill(color, y * width, y * width + width)
        }
        if (chrome) {
            // 顶部状态栏与底部导航栏是钉住的:两帧里都一样
            px.fill(0xFF123456.toInt(), 0, width * 10)
            px.fill(0xFF654321.toInt(), width * (height - 10), width * height)
        }
        return px
    }

    @Test fun shiftFindsHowFarTheContentMoved() {
        val prev = screen(0)
        val next = screen(120)
        assertEquals(120, LongShotMath.shift(prev, next, width, height, minOverlap = 40))
    }

    @Test fun shiftIgnoresPinnedChrome() {
        // 状态栏/导航栏完全一样,内容移动 90:仍然要认出 90
        assertEquals(90, LongShotMath.shift(screen(0), screen(90), width, height, minOverlap = 40))
    }

    @Test fun identicalFramesAreNoShift() {
        assertEquals(0, LongShotMath.shift(screen(0), screen(0), width, height, minOverlap = 40))
    }

    @Test fun ambiguousOrTinyMovesAreRejected() {
        // 纯色屏:每行都一样,没有唯一行可投票
        val flat = IntArray(width * height) { 0xFF888888.toInt() }
        assertEquals(0, LongShotMath.shift(flat, flat, width, height, minOverlap = 40))
        // 位移小于 MIN_SHIFT 当成没动
        assertEquals(0, LongShotMath.shift(screen(0), screen(5), width, height, minOverlap = 40))
        // 重叠不够(位移太大)也算失败
        assertEquals(0, LongShotMath.shift(screen(0), screen(390), width, height, minOverlap = 40))
    }

    @Test fun pickNeedsVotesAndDominance() {
        assertEquals(0, LongShotMath.pick(mapOf(100 to 5)))
        assertEquals(0, LongShotMath.pick(mapOf(100 to 30, 200 to 25)))
        assertEquals(100, LongShotMath.pick(mapOf(100 to 40, 200 to 10)))
    }

    @Test fun planCountsOnlyNewRowsAndSplitsSegments() {
        val plan = LongShotMath.plan(listOf(120, 120, 120), height = 400, segmentHeight = 500, maxTotal = 60_000)
        assertEquals(listOf(400, 120, 120, 120), plan.newRows)
        assertEquals(760, plan.height)
        assertEquals(listOf(500, 260), plan.segments.map { it.rows })
        assertEquals(2, plan.segments.size)
    }

    @Test fun planDropsBadShiftsAndRespectsTotalCap() {
        // 0 与超过屏高的位移不贡献新行
        val plan = LongShotMath.plan(listOf(0, 500), height = 400, segmentHeight = 500, maxTotal = 60_000)
        assertEquals(listOf(400, 0, 0), plan.newRows)
        assertEquals(400, plan.height)
        // 上限:总高被截到 maxTotal
        val capped = LongShotMath.plan(listOf(300, 300, 300), height = 400, segmentHeight = 500, maxTotal = 800)
        assertEquals(800, capped.height)
        assertTrue(capped.newRows.size <= 4)
    }
}
