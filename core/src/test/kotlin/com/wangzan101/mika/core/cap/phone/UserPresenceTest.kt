package com.wangzan101.mika.core.cap.phone

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test

/** 降级模式下等用户停手：只等、不抢，最多等上限。 */
class UserPresenceTest {

    @Test fun noTouchMeansGoRightAway() {
        assertEquals(0L, UserPresence.waitLeftMs(lastTouchAt = 0L, now = 1_000L))
    }

    @Test fun touchingNowMeansWaitTheFullQuietWindow() {
        assertEquals(UserPresence.QUIET_MS, UserPresence.waitLeftMs(lastTouchAt = 1_000L, now = 1_000L))
    }

    @Test fun nearlyQuietOnlyWaitsTheRest() {
        assertEquals(200L, UserPresence.waitLeftMs(lastTouchAt = 1_000L, now = 2_000L))
    }

    @Test fun quietEnoughMeansGoNow() {
        assertEquals(0L, UserPresence.waitLeftMs(lastTouchAt = 1_000L, now = 5_000L))
    }

    @Test fun awaitIdleReturnsZeroWhenNobodyIsTouching() = runTest {
        var now = 10_000L
        val waited = UserPresence.awaitIdle(
            lastTouchAt = { 0L },
            clock = { now },
            pause = { now += it },   // 时钟跟着暂停走
        )
        assertEquals(0L, waited)
    }

    @Test fun awaitIdleWaitsUntilTheQuietWindowPasses() = runTest {
        var now = 10_000L
        val waited = UserPresence.awaitIdle(
            lastTouchAt = { 9_500L },       // 500ms 前刚碰过
            clock = { now },
            pause = { now += it },
        )
        assertEquals(UserPresence.QUIET_MS - 500L, waited)   // 700ms
    }

    @Test fun awaitIdleGivesUpAtTheCapEvenIfTheyKeepTouching() = runTest {
        var now = 10_000L
        val waited = UserPresence.awaitIdle(
            lastTouchAt = { now },          // 一直有人在碰
            clock = { now },
            quietMs = 5_000L,
            maxWaitMs = 600L,
            pause = { now += it },
        )
        assertEquals(600L, waited)          // 上限到了就动手
    }

    @Test fun awaitIdleRestartsWhenTheUserTouchesAgain() = runTest {
        var now = 10_000L
        val touches = ArrayDeque(listOf(9_000L, 10_150L))   // 等过一次后又被碰了一下
        val waited = UserPresence.awaitIdle(
            lastTouchAt = { touches.removeFirstOrNull() ?: 10_150L },
            clock = { now },
            pause = { now += it },
        )
        // 第一轮等 150ms，这期间用户又碰了一下，之后重新计满 1200 → 共 1350
        assertEquals(1_350L, waited)
    }
}
