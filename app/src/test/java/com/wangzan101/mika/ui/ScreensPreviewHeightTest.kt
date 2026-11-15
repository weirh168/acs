package com.wangzan101.mika.ui

import androidx.compose.ui.unit.dp
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 小画面的四档高度。「满屏」要按手机可用高度算,不能写死:
 * 用户抱怨过「超大 800dp 也不是整块屏」,所以这里用屏幕高度减掉状态栏、标题栏和留白。
 */
class ScreensPreviewHeightTest {

    @Test fun fixedSizesKeepTheirHeights() {
        assertEquals(200.dp, previewHeight(PreviewSize.Small, 900))
        assertEquals(260.dp, previewHeight(PreviewSize.Medium, 900))
        assertEquals(460.dp, previewHeight(PreviewSize.Large, 900))
    }

    @Test fun fillScreenFollowsTheDevice() {
        assertEquals(750.dp, previewHeight(PreviewSize.Full, 900))     // 900 - 150
        assertEquals(936.dp, previewHeight(PreviewSize.Full, 1086))    // 常见 2400px/2.2 的手机
    }

    @Test fun fillScreenNeverFallsBelowTheLargeSize() {
        assertTrue(previewHeight(PreviewSize.Full, 600) >= 700.dp)
        assertTrue(previewHeight(PreviewSize.Full, 600) > previewHeight(PreviewSize.Large, 600))
    }

    @Test fun sizesAreOrdered() {
        val h = PreviewSize.entries.map { previewHeight(it, 900) }
        assertEquals(h.sorted(), h)
        assertEquals(4, h.distinct().size)
    }
}
