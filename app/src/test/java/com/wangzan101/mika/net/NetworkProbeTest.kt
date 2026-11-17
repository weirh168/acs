package com.wangzan101.mika.net

import org.junit.Assert.assertEquals
import org.junit.Test

class NetworkProbeTest {
    @Test fun successShowsSeconds() {
        assertEquals("0.4 秒", ProbeResult.summary(ProbeResult(true, 400, "")))
    }

    @Test fun failureShowsTheReason() {
        assertEquals("超时", ProbeResult.summary(ProbeResult(false, 5_000, "超时")))
        assertEquals("HTTP 404", ProbeResult.summary(ProbeResult(false, 120, "HTTP 404")))
    }
}
