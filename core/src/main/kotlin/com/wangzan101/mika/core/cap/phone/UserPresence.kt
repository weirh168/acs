package com.wangzan101.mika.core.cap.phone

import kotlinx.coroutines.delay

/**
 * 降级模式（操作的是用户自己的主屏）下的"手上有人的"判断。
 *
 * 用户在碰屏幕时我们不该同时动手：两边的动作会互相打断，比如我们正要点一个列表项，
 * 用户先一步滑了一下，点到的就是别的东西。所以动手前先看用户最后一次碰屏是什么时候，
 * 还在动就稍等，等到安静或超过上限为止。
 *
 * 只做等待、不做抢占：上限到了照样动手，宁可慢一点也不要一直卡住。
 */
object UserPresence {
    /** 用户最后一次碰屏之后，至少安静这么久才动手。 */
    const val QUIET_MS: Long = 1_200

    /** 最多等这么久；到点就动手。 */
    const val MAX_WAIT_MS: Long = 3_000

    /** 等的过程中隔多久看一眼。 */
    const val POLL_MS: Long = 150

    /** 还要再等多久才能动手；0 表示现在就可以。 */
    fun waitLeftMs(lastTouchAt: Long, now: Long, quietMs: Long = QUIET_MS): Long {
        if (lastTouchAt <= 0L) return 0L
        val left = lastTouchAt + quietMs - now
        return if (left > 0L) left else 0L
    }

    /**
     * 等到用户停下，最多等 [maxWaitMs]；返回实际等了多久（0 表示没等）。
     * [lastTouchAt] 每次调用都重新问，等待期间用户又碰了屏就重新计时。
     */
    suspend fun awaitIdle(
        lastTouchAt: () -> Long,
        clock: () -> Long = { System.currentTimeMillis() },
        quietMs: Long = QUIET_MS,
        maxWaitMs: Long = MAX_WAIT_MS,
        pause: suspend (Long) -> Unit = { delay(it) },
    ): Long {
        var waited = 0L
        while (true) {
            val left = waitLeftMs(lastTouchAt(), clock(), quietMs)
            if (left <= 0L) return waited
            if (waited >= maxWaitMs) return waited
            val step = minOf(left, POLL_MS, maxWaitMs - waited)
            pause(step)
            waited += step
        }
    }
}
