package com.wangzan101.mika.calls

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeoutOrNull
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream

/** Pipes carry 16 kHz input and 24 kHz output, PCM16 LE mono. Nothing is written to storage. */
internal class CallPcmBridge(
    private val capture: InputStream,
    private val playback: OutputStream,
    private val interruptPlayback: suspend () -> Boolean,
) {
    suspend fun run(
        session: CallRealtimeSession,
        greeting: String,
        counters: CallMediaCounters?,
        onTranscript: (String, String) -> Unit,
        onFinalTranscript: (String, String) -> Unit = { _, _ -> },
        awaitFarewellDrain: suspend (CallFarewellFence) -> Boolean = { false },
        commitFarewell: () -> Boolean = { false },
    ): Unit = coroutineScope {
        val playbackQueue = CallPlaybackQueue()
        val writerLock = Mutex()
        val assistantText = StringBuilder()
        val farewell = CallFarewellPlayback()
        val finished = CompletableDeferred<Unit>()
        var farewellWaiter: Job? = null
        fun cancelFarewellWaiter() { farewellWaiter?.cancel(); farewellWaiter = null }
        fun checkFarewell() {
            val fence = farewell.takeFence() ?: return
            farewellWaiter = launch {
                if (awaitFarewellDrain(fence) && commitDrainedFarewell(commitFarewell)) finished.complete(Unit)
            }
        }

        fun flushAssistantText(completed: Boolean = false) {
            if (assistantText.isNotBlank()) {
                val text = assistantText.toString()
                onTranscript("assistant", text)
                if (completed) onFinalTranscript("assistant", text)
            }
            assistantText.clear()
        }
        // The separate writer leaves model event collection responsive when a pipe is full.
        val holdInput = java.util.concurrent.atomic.AtomicBoolean(false)
        val holdSince = java.util.concurrent.atomic.AtomicLong(0L)
        // 对方的声音在 AI 说话时先不送上去:既免回声,也免一句插话就把播报掐掉。说完立刻恢复。
        fun holdCallerInput() {
            holdInput.set(true)
            holdSince.set(System.nanoTime())
            // 本地不再上行,同时也让云端静音:双保险,避免回声把这一轮播报打断。
            runCatching { session.setMuted(true) }
        }
        // 释放必须幂等:任何一条结束路径(AI 说完、被取消、写线程退出、超时兜底)都会调它。
        fun releaseCallerInput() {
            if (holdInput.getAndSet(false)) {
                val held = System.nanoTime() - holdSince.get()
                if (held > 0) counters?.holdEnded(held)
                holdSince.set(0L)
            }
            runCatching { session.setMuted(false) }
        }
        val output = launch(Dispatchers.IO) {
            val pcm = ByteArray(CallPlaybackQueue.WRITE_BYTES)
            while (true) {
                val block = playbackQueue.take(pcm) ?: break
                try {
                    writerLock.withLock {
                        if (playbackQueue.isCurrent(block)) {
                            callPipeIo { playback.write(pcm, 0, block.byteCount) }
                            counters?.outputWritten(block.byteCount)
                        }
                    }
                } finally {
                    releaseCallerInput()
                    playbackQueue.release(block)
                }
            }
        }
        try {
            if (!session.setMuted(false) || (greeting.isNotBlank() && !session.sendGreeting(greeting))) {
                throw CallMediaFailure("火山未接受本次通话的开场白")
            }
            val input = launch(Dispatchers.IO) {
                val frame = ByteArray(session.inputChunkBytes)
                var position = 0
                while (true) {
                    val count = callPipeIo { capture.read(frame, position, frame.size - position) }
                    if (count < 0) throw CallMediaFailure("运营商音频输入已断开")
                    if (count == 0) continue
                    position += count
                    if (position == frame.size) {
                        counters?.inputRead()
                        // 兜底:AI 那头迟迟不发"说完了"(被取消、断线、丢帧)时,不能把上行一直掐着。
                        if (holdInput.get() && System.nanoTime() - holdSince.get() > HOLD_CALLER_INPUT_MAX_NS) {
                            releaseCallerInput()
                        }
                        if (!holdInput.get()) {
                            if (!session.sendPcm16(frame)) throw CallMediaFailure("火山音频输入已中断")
                            counters?.inputAccepted(frame, System.nanoTime())
                        } else {
                            counters?.inputSkippedWhileHeld()
                        }
                        position = 0
                    }
                }
            }
            val eventReader = launch {
                try {
                    session.events.collect { event ->
                        counters?.eventReceived(event)
                        when (event) {
                            is VolcRealtimeEvent.Audio -> {
                                val queuedBytes = playbackQueue.offer(event.pcm)
                                if (queuedBytes == null) {
                                    counters?.outputRejected()
                                    throw CallMediaFailure("通话待播音频积压超过安全上限，已交还系统")
                                }
                                cancelFarewellWaiter()
                                farewell.audio(event.pcm.size)
                                counters?.outputQueued(queuedBytes)
                            }
                            VolcRealtimeEvent.AssistantInterrupted -> {
                                cancelFarewellWaiter()
                                farewell.cancelCandidate()
                                if (farewell.hasPlaybackSinceFlush) {
                                    playbackQueue.invalidate()
                                    // First release any writer blocked on a full pipe. Flush again under
                                    // the writer lock to remove the last chunk that raced the first flush.
                                    val cleared = interruptPlayback() && withTimeoutOrNull(750) {
                                        writerLock.withLock { interruptPlayback() }
                                    } == true
                                    if (!cleared) throw CallMediaFailure("通话音频无法及时停止，已交还系统")
                                    farewell.afterPairedFlush()
                                }
                                // 播放已经冲掉,上行也必须放开:否则这一通电话之后 AI 永远听不到对方。
                                releaseCallerInput()
                                // Some providers report a second cancellation after user speech starts.
                                // Without newly accepted PCM, another flush would only reset the route.
                                flushAssistantText()
                            }
                            VolcRealtimeEvent.UserSpeaking -> {
                                // 对方开口不清空 AI 正在说的话,避免"对方一说话 AI 就哑了"
                                cancelFarewellWaiter()
                                farewell.cancelCandidate()
                            }
                            is VolcRealtimeEvent.UserTranscript -> {
                                cancelFarewellWaiter()
                                if (event.isFinal) {
                                    farewell.callerFinal(event.text, event.isCompleteFinal)
                                    onTranscript("caller", event.text)
                                    onFinalTranscript("caller", event.text)
                                } else farewell.cancelCandidate()
                            }
                            VolcRealtimeEvent.AssistantAudioStarted -> {
                                cancelFarewellWaiter()
                                farewell.audioStarted()
                                holdCallerInput()
                            }
                            VolcRealtimeEvent.AssistantAudioEnded -> {
                                farewell.audioEnded()
                                releaseCallerInput()
                                checkFarewell()
                            }
                            is VolcRealtimeEvent.AssistantTranscript -> {
                                val room = CallHistory.MAX_LINE_LENGTH - assistantText.length
                                if (room > 0) assistantText.append(event.delta.take(room))
                            }
                            VolcRealtimeEvent.AssistantTextEnded -> {
                                farewell.assistantFinal(assistantText.toString())
                                flushAssistantText(completed = true)
                                checkFarewell()
                            }
                            is VolcRealtimeEvent.Failed -> throw event.error
                            VolcRealtimeEvent.Closed -> throw CallMediaFailure("火山语音会话已结束，电话由系统处理")
                            else -> Unit
                        }
                    }
                    throw CallMediaFailure("火山语音连接已断开，电话由系统处理")
                } finally {
                    input.cancel()
                    flushAssistantText()
                }
            }
            try {
                // Keep the event reader active until the waiter actually issues the hangup.
                finished.await()
                eventReader.cancelAndJoin()
            } finally {
                cancelFarewellWaiter()
                eventReader.cancel()
            }
        } finally {
            // Closing both FDs is what releases a blocking read or write in a cancelled child.
            playbackQueue.close()
            output.cancel()
            runCatching { capture.close() }
            runCatching { playback.close() }
        }
    }
}

/** No suspension between checking for cancellation and committing on the call dispatcher. */
internal suspend fun commitDrainedFarewell(commit: () -> Boolean): Boolean {
    currentCoroutineContext().ensureActive()
    return commit()
}

/** AI 说话期间最多把上行掐这么久;超过就是它没发"说完了",当没在说话处理。 */
private const val HOLD_CALLER_INPUT_MAX_MS = 45_000L
private const val HOLD_CALLER_INPUT_MAX_NS = HOLD_CALLER_INPUT_MAX_MS * 1_000_000L

/** Bounded by time at 24 kHz PCM16 mono, independent of cloud packet boundaries. */
internal class CallPlaybackQueue(capacityBytes: Int = MAX_PENDING_BYTES) {
    data class Block(val generation: Int, val byteCount: Int)

    private val lock = Any()
    private val pcm = ByteArray(capacityBytes)
    private val signal = Channel<Unit>(Channel.CONFLATED)
    private var head = 0
    private var pending = 0
    private var writing = 0
    @Volatile private var generation = 0
    private var closed = false

    init { require(capacityBytes > 0 && capacityBytes % 2 == 0) }

    /** Returns occupied bytes, including the in-flight block; null means the packet did not fit. */
    fun offer(bytes: ByteArray): Int? = synchronized(lock) {
        if (closed || bytes.size % 2 != 0 || bytes.size > pcm.size - pending - writing) return null
        if (bytes.isEmpty()) return pending + writing
        val tail = (head + pending) % pcm.size
        val first = minOf(pcm.size - tail, bytes.size)
        bytes.copyInto(pcm, tail, 0, first)
        if (first < bytes.size) bytes.copyInto(pcm, 0, first)
        pending += bytes.size
        signal.trySend(Unit)
        pending + writing
    }

    /** One writer, at most one 20 ms block outside the ring. */
    suspend fun take(into: ByteArray): Block? {
        require(into.isNotEmpty() && into.size % 2 == 0)
        while (true) {
            synchronized(lock) {
                if (closed) return null
                check(writing == 0)
                if (pending > 0) {
                    val count = minOf(pending, into.size, WRITE_BYTES)
                    val first = minOf(pcm.size - head, count)
                    pcm.copyInto(into, 0, head, head + first)
                    if (first < count) pcm.copyInto(into, first, 0, count - first)
                    head = (head + count) % pcm.size
                    pending -= count
                    writing = count
                    return Block(generation, count)
                }
            }
            if (signal.receiveCatching().isClosed) return null
        }
    }

    fun isCurrent(block: Block): Boolean = generation == block.generation

    fun release(block: Block) = synchronized(lock) {
        if (isCurrent(block)) writing = 0
    }

    fun invalidate() = synchronized(lock) {
        generation++
        head = 0
        pending = 0
        writing = 0
    }

    fun close() = synchronized(lock) {
        closed = true
        invalidate()
        signal.close()
        Unit
    }

    companion object {
        private const val BYTES_PER_SECOND = VolcRealtimeClient.OUTPUT_SAMPLE_RATE * 2
        const val WRITE_BYTES = BYTES_PER_SECOND / 50
        // Covers short responses delivered faster than playback without an unbounded audio delay.
        const val MAX_PENDING_BYTES = BYTES_PER_SECOND * 8
    }
}

internal fun callAudioHasStarted(greeting: String, downBytes: Long, upBytes: Long): Boolean =
    downBytes > 0 && (greeting.isBlank() || upBytes > 0)

/** Closing a cancelled worker's pipe is expected; its IOException must not replace the cancellation. */
internal suspend inline fun <T> callPipeIo(action: () -> T): T {
    val context = currentCoroutineContext()
    context.ensureActive()
    val value = try {
        action()
    } catch (closed: IOException) {
        // Still surface real I/O faults while the call is active.
        context.ensureActive()
        throw closed
    }
    // A concurrently closed stream may report EOF instead of throwing.
    context.ensureActive()
    return value
}

internal class CallMediaFailure(message: String) : Exception(message)
