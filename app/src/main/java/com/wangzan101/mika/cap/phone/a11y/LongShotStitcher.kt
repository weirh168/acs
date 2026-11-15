package com.wangzan101.mika.cap.phone.a11y

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.Rect
import com.wangzan101.mika.core.visual.LongShotMath
import java.io.ByteArrayOutputStream

/**
 * 长截图的 Android 侧实现:把位图交给 [LongShotMath] 对齐(纯逻辑在 core,有 JVM 单测),
 * 这里只负责取像素、按规划把新行画进分段、压缩成 PNG。
 */
object LongShotStitcher {
    class Stitched(
        val segments: List<ByteArray>,
        val width: Int,
        val height: Int,
        val screens: Int,
        val overlaps: List<Int> = emptyList(),
        /** 中途停下时的原因(弹窗/遮罩/页面跳转),null 表示正常到底。 */
        val blocked: String? = null,
    )

    /** 对齐 [a] 与 [b]:内容向上移动了多少像素。逻辑在 [LongShotMath.shift]。 */
    fun shift(a: Bitmap, b: Bitmap, minOverlap: Int): Int {
        if (a.width != b.width || a.height != b.height) return 0
        val w = a.width
        val h = a.height
        val pa = IntArray(w * h)
        val pb = IntArray(w * h)
        a.getPixels(pa, 0, w, 0, 0, w, h)
        b.getPixels(pb, 0, w, 0, 0, w, h)
        val d = LongShotMath.shift(pa, pb, w, h, minOverlap)
        android.util.Log.i("MikaLongShot", "shift=$d of $h")
        return d
    }

    /**
     * 按 [shifts] 拼接:[shifts] 是相邻两帧的对齐位移。每帧只把底部新露出的行写进当前分段,
     * 段满 [LongShotMath.SEGMENT_HEIGHT] 就压缩输出。总高由 [LongShotMath.plan] 决定并封顶。
     */
    fun stitch(frames: List<Bitmap>, shifts: List<Int>, blocked: String? = null): Stitched? {
        if (frames.isEmpty()) return null
        val width = frames.first().width
        val height = frames.first().height
        if (frames.any { it.width != width || it.height != height }) return null

        val plan = LongShotMath.plan(shifts, height)
        if (plan.height > LongShotMath.MAX_TOTAL) return null

        val segments = mutableListOf<ByteArray>()
        val paint = Paint(Paint.FILTER_BITMAP_FLAG)
        var current: Bitmap? = null
        var canvas: Canvas? = null
        var offsetInSegment = 0

        fun finishSegment() {
            val bmp = current ?: return
            val out = ByteArrayOutputStream()
            bmp.compress(Bitmap.CompressFormat.PNG, 100, out)
            segments += out.toByteArray()
            bmp.recycle()
            current = null
            canvas = null
            offsetInSegment = 0
        }

        var written = 0
        try {
            frames.forEachIndexed { i, frame ->
                val newRows = plan.newRows.getOrElse(i) { 0 }
                if (newRows <= 0) return@forEachIndexed
                val srcTop = height - newRows
                var consumed = 0
                while (consumed < newRows) {
                    if (current == null) {
                        val room = minOf(LongShotMath.SEGMENT_HEIGHT, plan.height - written).coerceAtLeast(1)
                        current = Bitmap.createBitmap(width, room, Bitmap.Config.ARGB_8888)
                        canvas = Canvas(current!!)
                        offsetInSegment = 0
                    }
                    val room = current!!.height - offsetInSegment
                    val take = minOf(room, newRows - consumed)
                    canvas!!.drawBitmap(
                        frame,
                        Rect(0, srcTop + consumed, width, srcTop + consumed + take),
                        Rect(0, offsetInSegment, width, offsetInSegment + take),
                        paint,
                    )
                    consumed += take
                    offsetInSegment += take
                    written += take
                    if (offsetInSegment >= current!!.height) finishSegment()
                }
            }
            finishSegment()
            if (segments.isEmpty()) return null
            return Stitched(segments, width, written, frames.size, shifts, blocked)
        } catch (e: Throwable) {
            current?.recycle()
            return null
        }
    }

    /** 把帧转 90°(横向长截图用:先转成竖的,拼完再转回来)。 */
    fun rotate(frame: Bitmap, clockwise: Boolean): Bitmap {
        val m = Matrix()
        m.postRotate(if (clockwise) 90f else -90f)
        return Bitmap.createBitmap(frame, 0, 0, frame.width, frame.height, m, true)
    }
}
