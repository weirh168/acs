package com.wangzan101.mika.voice

import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.io.ByteArrayOutputStream

/**
 * 按住/点一下说话,把一段麦克风录音直接转成文字。
 *
 * 和「通话后转写」共用同一条识别链路(见 [Transcriber]),区别只是音频来自当场录音
 * 而不是系统通话录音文件。录音固定 16 kHz / 单声道 / 16 bit,正好是识别服务要的格式。
 */
object Dictation {
    private const val RATE = 16000
    private const val MAX_MS = 60_000

    /** 录一段并返回 WAV 字节;没录到声音返回 null。 */
    fun record(maxMs: Int = MAX_MS, stop: () -> Boolean): ByteArray? {
        val min = AudioRecord.getMinBufferSize(RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        if (min <= 0) return null
        val rec = AudioRecord(
            MediaRecorder.AudioSource.MIC, RATE,
            AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, min * 4,
        )
        if (rec.state != AudioRecord.STATE_INITIALIZED) {
            runCatching { rec.release() }
            return null
        }
        val pcm = ByteArrayOutputStream()
        val buf = ByteArray(4096)
        val startedAt = System.currentTimeMillis()
        runCatching {
            rec.startRecording()
            while (!stop() && System.currentTimeMillis() - startedAt < maxMs) {
                val n = rec.read(buf, 0, buf.size)
                if (n > 0) pcm.write(buf, 0, n)
            }
        }
        runCatching {
            rec.stop()
            rec.release()
        }
        val body = pcm.toByteArray()
        if (body.size < RATE / 2) return null // 不到半秒当没说话
        return wav(body)
    }

    /** 把 PCM 包成 16 kHz 单声道 WAV。 */
    fun wav(pcm: ByteArray): ByteArray {
        val out = ByteArrayOutputStream(44 + pcm.size)
        fun le32(v: Int) = byteArrayOf(
            (v and 0xFF).toByte(), ((v shr 8) and 0xFF).toByte(),
            ((v shr 16) and 0xFF).toByte(), ((v shr 24) and 0xFF).toByte(),
        )
        fun le16(v: Int) = byteArrayOf((v and 0xFF).toByte(), ((v shr 8) and 0xFF).toByte())
        out.write("RIFF".toByteArray()); out.write(le32(36 + pcm.size))
        out.write("WAVE".toByteArray()); out.write("fmt ".toByteArray())
        out.write(le32(16)); out.write(le16(1)); out.write(le16(1))
        out.write(le32(RATE)); out.write(le32(RATE * 2)); out.write(le16(2)); out.write(le16(16))
        out.write("data".toByteArray()); out.write(le32(pcm.size)); out.write(pcm)
        return out.toByteArray()
    }
}