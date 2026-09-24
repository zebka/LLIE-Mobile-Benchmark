package org.llie.mobilebenchmark.runner

import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File
import java.nio.file.Files

class ResolveImageFilesTest {

    @Test
    fun explicitNamesWinOverListingAndKeepOrder() {
        val dir = Files.createTempDirectory("images").toFile()
        File(dir, "b.png").writeText("b")
        File(dir, "a.png").writeText("a")
        val resolved = BenchmarkExecutor.resolveImageFiles(dir, listOf("b.png", "a.png"))
        assertEquals(listOf("b.png", "a.png"), resolved.map { it.name })
    }

    @Test
    fun nullNamesFallBackToSortedPngListing() {
        val dir = Files.createTempDirectory("images").toFile()
        File(dir, "b.png").writeText("b")
        File(dir, "a.png").writeText("a")
        File(dir, "note.txt").writeText("x")
        val resolved = BenchmarkExecutor.resolveImageFiles(dir, null)
        assertEquals(listOf("a.png", "b.png"), resolved.map { it.name })
    }

    @Test
    fun emptyNamesFallBackToListing() {
        val dir = Files.createTempDirectory("images").toFile()
        File(dir, "a.png").writeText("a")
        val resolved = BenchmarkExecutor.resolveImageFiles(dir, emptyList())
        assertEquals(listOf("a.png"), resolved.map { it.name })
    }
}
