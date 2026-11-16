package com.wangzan101.mika.core.trace

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.util.zip.ZipFile

class TraceStoreExportTest {
    @get:Rule val tmp = TemporaryFolder()

    @Test fun exportZipPacksEveryRunUnderItsOwnFolder() {
        val root = tmp.newFolder("harness-traces")
        val run = File(root, "run-1")
        run.mkdirs()
        File(run, "spans.json").writeText("[]")
        File(File(run, "blocks"), "b1").apply { parentFile!!.mkdirs() }.writeText("x")
        val store = TraceStore(root)

        val zip = store.exportZip(File(tmp.root, "out.zip"))
        assertTrue(zip.isFile)
        ZipFile(zip).use { z ->
            val names = z.entries().asSequence().map { it.name }.toList()
            assertEquals(2, names.size)
            assertTrue(names.any { it == "run-1/spans.json" })
            assertTrue(names.any { it == "run-1/blocks/b1" })
        }
    }
}
