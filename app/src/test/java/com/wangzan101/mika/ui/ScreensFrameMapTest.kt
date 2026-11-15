package com.wangzan101.mika.ui

import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * 「我来操作」那层要把手指位置换算回画面像素:画面按 Fit 显示,四边留白要减掉,
 * 否则点哪儿都偏;点在留白里应当当作没点,不能下发到屏上。
 */
class ScreensFrameMapTest {

    // 手机屏 1080×2400 显示在一个 1000×1000 的框里:高度受限,左右留白各 (1000-450)/2 = 275
    private val box = Size(1000f, 1000f)
    private val frameW = 1080
    private val frameH = 2400

    @Test fun centerOfFrameMapsToCenterOfScreen() {
        val p = mapToFrame(Offset(500f, 500f), box, frameW, frameH)
        assertEquals(540f, p!!.x, 0.5f)
        assertEquals(1200f, p.y, 0.5f)
    }

    @Test fun topLeftOfPaintedAreaMapsToZero() {
        val p = mapToFrame(Offset(275f, 0f), box, frameW, frameH)
        assertEquals(0f, p!!.x, 0.5f)
        assertEquals(0f, p.y, 0.5f)
    }

    @Test fun bottomRightOfPaintedAreaMapsToFrameSize() {
        val p = mapToFrame(Offset(725f, 1000f), box, frameW, frameH)
        assertEquals(1080f, p!!.x, 0.5f)
        assertEquals(2400f, p.y, 0.5f)
    }

    @Test fun tapsInTheLetterboxAreIgnored() {
        assertNull(mapToFrame(Offset(100f, 500f), box, frameW, frameH))
        assertNull(mapToFrame(Offset(900f, 500f), box, frameW, frameH))
        assertNull(mapToFrame(Offset(500f, -10f), box, frameW, frameH))
    }

    @Test fun unmeasuredBoxOrFrameIsIgnored() {
        assertNull(mapToFrame(Offset(1f, 1f), Size.Zero, frameW, frameH))
        assertNull(mapToFrame(Offset(1f, 1f), box, 0, 0))
    }

    @Test fun wideFrameIsLetterboxedVertically() {
        // 1920×1080 的横屏画面放进 1000×1000:上下留白各 (1000-562.5)/2 = 218.75
        val p = mapToFrame(Offset(500f, 500f), box, 1920, 1080)
        assertEquals(960f, p!!.x, 0.5f)
        assertEquals(540f, p.y, 0.5f)
        assertNull(mapToFrame(Offset(500f, 100f), box, 1920, 1080))
    }
}
