package com.wangzan101.mika.core.trace

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class TraceStoreClearTest {
    @get:Rule val tmp = TemporaryFolder()

    @Test fun clearRemovesEveryRunButKeepsTheRoot() {
        val root = tmp.newFolder("harness-traces")
        File(root, "run-1").mkdirs()
        File(File(root, "run-1"), "spans").mkdirs()
        File(root, "run-2").mkdirs()
        val store = TraceStore(root)

        assertEquals(2, store.clear())
        assertTrue(root.isDirectory)
        assertEquals(0, root.listFiles()?.size ?: 0)
    }

    @Test fun usedBytesCountsFilesUnderRuns() {
        val root = tmp.newFolder("harness-traces")
        val run = File(root, "run-1")
        run.mkdirs()
        File(run, "a.bin").writeBytes(ByteArray(64))
        val store = TraceStore(root)
        assertEquals(64L, store.usedBytes())
        store.clear()
        assertEquals(0L, store.usedBytes())
    }
}
