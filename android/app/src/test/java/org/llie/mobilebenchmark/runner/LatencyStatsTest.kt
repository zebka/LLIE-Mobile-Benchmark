package org.llie.mobilebenchmark.runner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class LatencyStatsTest {

    @Test
    fun summarizeUsesMedianAndNearestRankP95() {
        val summary = LatencyStats.summarize(listOf(1L, 2L, 3L, 4L))
        assertEquals(2.5, summary.medianNs, 0.0)
        assertEquals(4L, summary.p95Ns)
    }

    @Test
    fun summarizeHandlesOddCount() {
        val summary = LatencyStats.summarize(listOf(10L, 20L, 30L))
        assertEquals(20.0, summary.medianNs, 0.0)
        assertEquals(30L, summary.p95Ns)
    }

    @Test
    fun summarizeRejectsEmptyList() {
        assertThrows(IllegalArgumentException::class.java) {
            LatencyStats.summarize(emptyList())
        }
    }

    @Test
    fun summarizeSingleSample() {
        val summary = LatencyStats.summarize(listOf(42L))
        assertEquals(42.0, summary.medianNs, 0.0)
        assertEquals(42L, summary.p95Ns)
    }
}
