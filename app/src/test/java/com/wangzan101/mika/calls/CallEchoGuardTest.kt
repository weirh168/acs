package com.wangzan101.mika.calls

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Random
import kotlin.math.PI
import kotlin.math.sin

/**
 * 回声识别器的行为:自己刚播出去的声音要被认出来,别人的声音不能被误杀。
 * 这是通话能不能对答的关键一步,所以用合成信号写死预期。
 */
class CallEchoGuardTest {

    /** 24 kHz 的「AI 说话」:几个不同频率叠起来的类语音信号。 */
    private fun speech24(samples: Int, seed: Int = 1): ByteArray {
        val rnd = Random(seed.toLong())
        val out = ByteArray(samples * 2)
        for (i in 0 until samples) {
            val t = i / 24_000.0
            val v = (0.45 * sin(2 * PI * 180 * t) + 0.3 * sin(2 * PI * 420 * t) + 0.15 * sin(2 * PI * 900 * t)) * 20_000 +
                rnd.nextGaussian() * 200
            val s = v.toInt().coerceIn(-32768, 32767)
            out[i * 2] = (s and 0xff).toByte()
            out[i * 2 + 1] = ((s shr 8) and 0xff).toByte()
        }
        return out
    }

    /**
     * 把 24 kHz 的播放信号按 3:2 重采样成 16 kHz,并整体延迟 [delay16] 个 16 kHz 采样(模拟回声晚到)。
     * 注意延迟是按输出采样算的:先算源位置再取样本,别把两种采样率的索引混用。
     */
    private fun downlink16(source24: ByteArray, delay16: Int, gain: Double): ByteArray {
        val srcSamples = source24.size / 2
        val outSamples = (srcSamples / 1.5).toInt()
        val out = ByteArray(outSamples * 2)
        for (i in 0 until outSamples) {
            val src = (i - delay16) * 1.5
            val v = if (src < 0.0 || src >= srcSamples - 1) 0.0 else {
                val idx = src.toInt()
                val frac = src - idx
                val a = ((source24[idx * 2].toInt() and 0xff) or (source24[idx * 2 + 1].toInt() shl 8)).toShort().toInt()
                val b = ((source24[(idx + 1) * 2].toInt() and 0xff) or (source24[(idx + 1) * 2 + 1].toInt() shl 8)).toShort().toInt()
                (a * (1.0 - frac) + b * frac) * gain
            }
            val clamped = v.toInt().coerceIn(-32768, 32767)
            out[i * 2] = (clamped and 0xff).toByte()
            out[i * 2 + 1] = ((clamped shr 8) and 0xff).toByte()
        }
        return out
    }

    private fun noise16(samples: Int, seed: Int): ByteArray {
        val rnd = Random(seed.toLong())
        val out = ByteArray(samples * 2)
        for (i in 0 until samples) {
            val s = (rnd.nextGaussian() * 9_000).toInt().coerceIn(-32768, 32767)
            out[i * 2] = (s and 0xff).toByte()
            out[i * 2 + 1] = ((s shr 8) and 0xff).toByte()
        }
        return out
    }

    @Test
    fun ownPlaybackComesBackAsEcho() {
        val guard = CallEchoGuard()
        val ai = speech24(24_000)                       // 1 秒
        guard.remember(ai, ai.size)
        // 真实通话里回声是紧跟在播放尾巴后面的,所以取最后 20 ms(延迟在 downlink16 里加)
        val all = downlink16(ai, delay16 = 40, gain = 0.5)
        val echo = all.copyOfRange(all.size - 320 * 2, all.size)
        assertTrue("自己刚播出去的声音应判为回声", guard.isEcho(echo))
    }

    @Test
    fun otherVoiceIsNotEcho() {
        val guard = CallEchoGuard()
        val ai = speech24(24_000, seed = 7)
        guard.remember(ai, ai.size)
        val caller = noise16(320, seed = 42)
        assertFalse("别人的声音不能被误判成回声", guard.isEcho(caller))
    }

    @Test
    fun silenceIsNotEcho() {
        val guard = CallEchoGuard()
        val ai = speech24(24_000)
        guard.remember(ai, ai.size)
        assertFalse("静音不该被当成回声(能量不足直接跳过)", guard.isEcho(ByteArray(320)))
    }

    @Test
    fun quietEchoStillRecognised() {
        // 回声被系统压低到很小也要认出来,否则会把 AI 自己的尾巴当对方说话
        val guard = CallEchoGuard()
        val ai = speech24(24_000, seed = 3)
        guard.remember(ai, ai.size)
        val all = downlink16(ai, delay16 = 90, gain = 1.0)
        val echo = all.copyOfRange(all.size - 320 * 2, all.size)
        assertTrue(guard.isEcho(echo))
    }
}
