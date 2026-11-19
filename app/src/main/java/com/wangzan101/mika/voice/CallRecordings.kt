package com.wangzan101.mika.voice

import android.content.Context
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.net.Uri
import android.provider.MediaStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * 系统通话录音(Voice Record 之类)所在目录。荣耀/华为把录音放这里:
 * /sdcard/Sounds/CallRecord/<名字>_<时间>.m4a
 */
object CallRecordings {
    private const val DIR = "Sounds/CallRecord"

    data class Item(val uri: Uri, val name: String, val dateMs: Long)

    /** 最近的一条通话录音;MediaStore 没索引到就直接读目录。都没有时 null。 */
    fun latest(context: Context): Item? = query(context).firstOrNull() ?: latestFile()

    /** MediaStore 常常没索引这个目录,直接扫文件更可靠(需要读取音频权限)。 */
    private fun latestFile(): Item? = runCatching {
        val dir = File("/sdcard/" + DIR)
        if (!dir.isDirectory) return null
        dir.listFiles { f -> f.isFile && f.name.endsWith(".m4a", true) }
            ?.maxByOrNull { it.lastModified() }
            ?.let { Item(Uri.fromFile(it), it.name, it.lastModified()) }
    }.getOrNull()

    /** 目录里所有录音,新的在前。 */
    fun query(context: Context): List<Item> {
        val items = mutableListOf<Item>()
        val cols = arrayOf(MediaStore.Audio.Media._ID, MediaStore.Audio.Media.DISPLAY_NAME, MediaStore.Audio.Media.DATE_ADDED)
        val where = if (android.os.Build.VERSION.SDK_INT >= 29) {
            MediaStore.Audio.Media.RELATIVE_PATH + " LIKE ?"
        } else {
            MediaStore.Audio.Media.DATA + " LIKE ?"
        }
        runCatching {
            context.contentResolver.query(
                MediaStore.Audio.Media.EXTERNAL_CONTENT_URI, cols, where, arrayOf("%" + DIR + "%"),
                MediaStore.Audio.Media.DATE_ADDED + " DESC",
            )?.use { c ->
                val idCol = c.getColumnIndexOrThrow(cols[0])
                val nameCol = c.getColumnIndexOrThrow(cols[1])
                val dateCol = c.getColumnIndexOrThrow(cols[2])
                while (c.moveToNext() && items.size < 200) {
                    val id = c.getLong(idCol)
                    items += Item(
                        android.content.ContentUris.withAppendedId(MediaStore.Audio.Media.EXTERNAL_CONTENT_URI, id),
                        c.getString(nameCol).orEmpty(),
                        c.getLong(dateCol) * 1000,
                    )
                }
            }
        }
        return items
    }

    /** 把一条录音解成 16k 单声道 WAV:各家识别接口只收 WAV。 */
    fun toWav(context: Context, uri: Uri): ByteArray? = runCatching {
        val extractor = MediaExtractor()
        val pfd = if (uri.scheme == "file") null else context.contentResolver.openFileDescriptor(uri, "r")
        if (pfd != null) extractor.setDataSource(pfd.fileDescriptor) else extractor.setDataSource(uri.path!!)
        var track = -1
        var format: MediaFormat? = null
        for (i in 0 until extractor.trackCount) {
            val f = extractor.getTrackFormat(i)
            if (f.getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true) { track = i; format = f; break }
        }
        if (track < 0 || format == null) { extractor.release(); pfd?.close(); return null }
        extractor.selectTrack(track)
        val mime = format.getString(MediaFormat.KEY_MIME)!!
        val sampleRate = format.getInteger(MediaFormat.KEY_SAMPLE_RATE)
        val channels = format.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
        val codec = MediaCodec.createDecoderByType(mime)
        codec.configure(format, null, null, 0)
        codec.start()
        val pcm = java.io.ByteArrayOutputStream()
        val info = MediaCodec.BufferInfo()
        var sawInput = false
        var sawOutput = false
        while (!sawOutput) {
            if (!sawInput) {
                val inIndex = codec.dequeueInputBuffer(10_000)
                if (inIndex >= 0) {
                    val buf = codec.getInputBuffer(inIndex)!!
                    val size = extractor.readSampleData(buf, 0)
                    if (size < 0) {
                        codec.queueInputBuffer(inIndex, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                        sawInput = true
                    } else {
                        codec.queueInputBuffer(inIndex, 0, size, extractor.sampleTime, 0)
                        extractor.advance()
                    }
                }
            }
            val outIndex = codec.dequeueOutputBuffer(info, 10_000)
            if (outIndex >= 0) {
                val out = codec.getOutputBuffer(outIndex)!!
                out.position(info.offset); out.limit(info.offset + info.size)
                val chunk = ByteArray(info.size)
                out.get(chunk)
                pcm.write(chunk)
                codec.releaseOutputBuffer(outIndex, false)
                if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) sawOutput = true
            }
        }
        codec.stop(); codec.release(); extractor.release(); pfd?.close()
        val raw = pcm.toByteArray()
        val shorts = ShortArray(raw.size / 2)
        ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().get(shorts)
        return resample(downmix(shorts, channels), sampleRate, 16000)
    }.getOrNull()

    private fun downmix(src: ShortArray, channels: Int): ShortArray {
        if (channels <= 1) return src
        val frames = src.size / channels
        val out = ShortArray(frames)
        for (i in 0 until frames) {
            var sum = 0
            for (c in 0 until channels) sum += src[i * channels + c]
            out[i] = (sum / channels).toShort()
        }
        return out
    }

    private fun resample(src: ShortArray, from: Int, to: Int): ByteArray {
        val out = if (from == to) src else {
            val n = (src.size.toLong() * to / from).toInt().coerceAtLeast(1)
            ShortArray(n) { i ->
                val pos = i.toDouble() * from / to
                val i0 = pos.toInt().coerceIn(0, src.size - 1)
                src[i0]
            }
        }
        val buf = ByteBuffer.allocate(44 + out.size * 2).order(ByteOrder.LITTLE_ENDIAN)
        val dataLen = out.size * 2
        buf.put("RIFF".toByteArray()); buf.putInt(36 + dataLen); buf.put("WAVE".toByteArray())
        buf.put("fmt ".toByteArray()); buf.putInt(16); buf.putShort(1); buf.putShort(1)
        buf.putInt(to); buf.putInt(to * 2); buf.putShort(2); buf.putShort(16)
        buf.put("data".toByteArray()); buf.putInt(dataLen)
        out.forEach { buf.putShort(it) }
        return buf.array()
    }

    /** 目录存在但没文件时的提示用。 */
    fun dirExists(): Boolean = File("/sdcard/" + DIR).exists()
}