package org.llie.mobilebenchmark.runner

import kotlin.math.ceil

/** Deterministic latency aggregation for the benchmark protocol. */
object LatencyStats {

    data class LatencySummary(val medianNs: Double, val p95Ns: Long)

    fun summarize(samplesNs: List<Long>): LatencySummary {
        require(samplesNs.isNotEmpty()) { "latency samples must not be empty" }
        val ordered = samplesNs.sorted()
        val n = ordered.size
        val median = if (n % 2 == 1) {
            ordered[n / 2].toDouble()
        } else {
            (ordered[n / 2 - 1].toDouble() + ordered[n / 2].toDouble()) / 2.0
        }
        val rank = ceil(0.95 * n).toInt().coerceIn(1, n)
        return LatencySummary(medianNs = median, p95Ns = ordered[rank - 1])
    }
}
