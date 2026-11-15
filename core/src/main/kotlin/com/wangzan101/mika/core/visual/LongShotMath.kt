package com.wangzan101.mika.core.visual

/**
 * 长截图的对齐与拼接规划,只用整数像素数组,不碰 Android 的 Bitmap,所以能在 JVM 上单测。
 *
 * 对齐做法:把每一行压成指纹(横向抽样、通道量化),相邻两帧的行指纹互相投票——
 * 上一帧行 y 与下一帧行 z 指纹相同,就给位移 `y - z` 投一票。得票最多且明显领先的位移就是实际滚了多少,
 * 滚动中变了的部分(折叠标题栏、状态栏、加载动画)只是不投票。
 */
object LongShotMath {
    /** 一行抽多少列做指纹。 */
    const val SAMPLE_COLUMNS = 24
    /** 通道值量化级数,容忍轻微抗锯齿差异。 */
    const val QUANTIZE = 24
    /** 状态栏与底部导航栏钉住不动,不参与投票(占屏高比例)。 */
    const val CHROME_RATIO = 0.055
    /** 至少这么多行投同一个位移才认。 */
    const val MIN_VOTES = 20
    /** 位移小于这么多像素就当没动。 */
    const val MIN_SHIFT = 32
    /** 第一名票数要达到第二名的这个倍数,否则认为有歧义。 */
    const val VOTE_DOMINANCE = 1.5
    /** 每一段最多多高。 */
    const val SEGMENT_HEIGHT = 8_000
    /** 总共最多多少像素。 */
    const val MAX_TOTAL = 60_000

    /** 一行的指纹:按 [SAMPLE_COLUMNS] 抽样、每通道量化后混成一个 long。 */
    fun rowSignature(pixels: IntArray, offset: Int, width: Int): Long {
        var hash = 1125899906842597L
        val step = (width / SAMPLE_COLUMNS).coerceAtLeast(1)
        var x = 0
        while (x < width) {
            val c = pixels[offset + x]
            val r = ((c shr 16) and 0xFF) / QUANTIZE
            val g = ((c shr 8) and 0xFF) / QUANTIZE
            val b = (c and 0xFF) / QUANTIZE
            hash = hash * 31 + (r * 31 + g) * 31 + b
            x += step
        }
        return hash
    }

    /**
     * 内容在 [next] 里相对 [prev] 向上移动了多少像素(即 next 的第 0 行对应 prev 的第 d 行)。
     * 对不上、位移太小、或证据有歧义时返回 0。
     * [minOverlap] 是这次拼接要求的最少重叠像素。
     */
    fun shift(prev: IntArray, next: IntArray, width: Int, height: Int, minOverlap: Int): Int {
        if (width <= 0 || height <= 0) return 0
        if (prev.size < width * height || next.size < width * height) return 0
        val chromeTop = (height * CHROME_RATIO).toInt()
        val chromeBottom = (height * CHROME_RATIO).toInt()
        val from = chromeTop
        val to = height - chromeBottom
        if (to - from < 32) return 0

        val sigPrev = LongArray(to - from) { rowSignature(prev, (from + it) * width, width) }
        val sigNext = LongArray(to - from) { rowSignature(next, (from + it) * width, width) }
        val countPrev = HashMap<Long, Int>(sigPrev.size)
        for (sig in sigPrev) countPrev[sig] = (countPrev[sig] ?: 0) + 1
        val countNext = HashMap<Long, Int>(sigNext.size)
        for (sig in sigNext) countNext[sig] = (countNext[sig] ?: 0) + 1

        // 先用「两帧里都只出现一次」的行投票:成排的分隔线、纯色行不参与,免得投出假位移。
        for (maxRepeat in intArrayOf(1, 2)) {
            val index = HashMap<Long, Int>(sigPrev.size)
            sigPrev.forEachIndexed { i, sig -> if (countPrev[sig]!! <= maxRepeat) index[sig] = from + i }
            val votes = HashMap<Int, Int>()
            sigNext.forEachIndexed { i, sig ->
                if (countNext[sig]!! > maxRepeat) return@forEachIndexed
                val y = index[sig] ?: return@forEachIndexed
                val z = from + i
                val d = y - z
                if (d < MIN_SHIFT || d > height - minOverlap) return@forEachIndexed
                votes[d] = (votes[d] ?: 0) + 1
            }
            val picked = pick(votes)
            if (picked > 0) return picked
        }
        return 0
    }

    /** 得票最多、且明显领先第二名的位移;不够可信返回 0。 */
    fun pick(votes: Map<Int, Int>): Int {
        if (votes.isEmpty()) return 0
        val ranked = votes.entries.sortedByDescending { it.value }
        val best = ranked.first()
        val second = ranked.getOrNull(1)?.value ?: 0
        if (best.value < MIN_VOTES) return 0
        if (second > 0 && best.value < second * VOTE_DOMINANCE) return 0
        return best.key
    }

    /**
     * 拼接规划:第 i 帧要写进去的新行数(首帧是整幅高;其余是它底部新露出的 d 行),
     * 以及按 [segmentHeight] 切出来的段([Segment.rows] 是这一段的行数,[Segment.sourceRows] 是各帧贡献的行数,顺序与 [newRows] 对应)。
     */
    data class Plan(val newRows: List<Int>, val height: Int, val segments: List<Segment>)

    data class Segment(val sourceRows: List<Int>, val rows: Int)

    /**
     * 算每帧贡献多少行、总共多高、分几段。位移为 0 或超过屏高时按 0 处理(不贡献新行)。
     * 总高超过 [maxTotal] 时截断:`truncated` 为 true。
     */
    fun plan(shifts: List<Int>, height: Int, segmentHeight: Int = SEGMENT_HEIGHT, maxTotal: Int = MAX_TOTAL): Plan {
        var total = height
        val newRows = ArrayList<Int>(shifts.size + 1)
        newRows += height
        for (d in shifts) {
            val rows = if (d <= 0 || d > height) 0 else d
            if (total + rows > maxTotal) {
                val room = (maxTotal - total).coerceAtLeast(0)
                newRows += room
                total += room
                break
            }
            newRows += rows
            total += rows
        }
        val segments = mutableListOf<Segment>()
        var remaining = total
        while (remaining > 0) {
            val rows = minOf(remaining, segmentHeight)
            segments += Segment(sourceRows = newRows, rows = rows)
            remaining -= rows
        }
        return Plan(newRows, total, segments)
    }
}
