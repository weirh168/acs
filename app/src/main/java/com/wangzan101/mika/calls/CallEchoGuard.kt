package com.wangzan101.mika.calls

import kotlin.math.abs

/**
 * 通话里「自己在说话」的识别器。
 *
 * 走 VOICE_CALL 采集时，采回来的混音轨里既有对方，也有我们自己刚播出去的声音。只按时间掐上行
 * （AI 说话期间不发）会把对方的话一起挡掉，放得太松又会把 AI 自己的话识别成对方在说。这里改成
 * 按波形判断：把刚播出去的音频留一小段做参考，采到一帧就和参考做归一化互相关，像自己刚说过的话
 * 就丢掉，其余照常上行。
 *
 * 播放是 24 kHz、上行是 16 kHz，参考按 3:2 线性插值降到 16 kHz。只留最近 [referenceMs] 毫秒，
 * 足够覆盖扬声器到麦克风的延迟和一点点抖动。
 */
internal class CallEchoGuard(
    private val inputRate: Int = VolcRealtimeClient.INPUT_SAMPLE_RATE,
    outputRate: Int = VolcRealtimeClient.OUTPUT_SAMPLE_RATE,
    referenceMs: Int = 700,
) {
    private val ratio = outputRate.toDouble() / inputRate
    private val ring = ShortArray((inputRate * referenceMs / 1000).coerceAtLeast(inputRate / 4))
    private var head = 0
    private var filled = 0

    /** 把刚写进通话的 24 kHz 音频记进参考；只读前 [byteCount] 字节。 */
    @Synchronized
    fun remember(pcm24: ByteArray, byteCount: Int) {
        val samples = byteCount / 2
        if (samples < 2) return
        var out = 0.0
        while (out < samples / ratio) {
            val src = out * ratio
            val i = src.toInt()
            if (i + 1 >= samples) break
            val frac = src - i
            val a = sampleAt(pcm24, i)
            val b = sampleAt(pcm24, i + 1)
            val v = (a * (1.0 - frac) + b * frac).toInt().coerceIn(-32768, 32767)
            ring[head] = v.toShort()
            head = (head + 1) % ring.size
            if (filled < ring.size) filled++
            out += 1.0
        }
    }

    /** 这一帧看起来像不像我们刚播出去的声音。参考还没攒够时一律说「不像」。 */
    @Synchronized
    fun isEcho(frame: ByteArray): Boolean {
        val n = frame.size / 2
        if (n < 64 || filled < n * 2) return false
        var energy = 0.0
        var i = 0
        while (i < n) {
            val s = sampleAt(frame, i).toDouble()
            energy += s * s
            i++
        }
        if (energy < MIN_ENERGY) return false
        val norm = Math.sqrt(energy)
        // 参考里按滞后找最像的一段:扬声器到麦克风的延迟通常几毫秒到一两百毫秒
        var best = 0.0
        var lag = 0
        while (lag <= maxLag(n)) {
            var dot = 0.0
            var refEnergy = 0.0
            i = 0
            while (i < n) {
                val idx = (head - n - lag + i).let { if (it < 0) it + ring.size else it } % ring.size
                val r = ring[idx].toDouble()
                dot += sampleAt(frame, i) * r
                refEnergy += r * r
                i++
            }
            if (refEnergy > 0.0) {
                val corr = dot / (norm * Math.sqrt(refEnergy))
                if (corr > best) best = corr
            }
            lag += LAG_STEP
        }
        return best >= THRESHOLD
    }

    private fun maxLag(n: Int): Int = (ring.size - n - 1).coerceAtMost(LAG_MAX).coerceAtLeast(0)

    private fun sampleAt(bytes: ByteArray, index: Int): Int {
        val at = index * 2
        if (at + 1 >= bytes.size) return 0
        return ((bytes[at].toInt() and 0xff) or (bytes[at + 1].toInt() shl 8)).toShort().toInt()
    }

    companion object {
        /** 归一化互相关到这个程度就认定是自己刚说的。 */
        private const val THRESHOLD = 0.42
        /** 帧能量太低(静音)不做判断。 */
        private const val MIN_ENERGY = 800_000.0
        /** 最大滞后采样数(16 kHz 下约 120 ms)。 */
        private const val LAG_MAX = 1_900
        private const val LAG_STEP = 8
    }
}
