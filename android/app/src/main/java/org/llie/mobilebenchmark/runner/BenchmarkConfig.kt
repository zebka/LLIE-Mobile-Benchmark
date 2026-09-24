package org.llie.mobilebenchmark.runner

/**
 * Frozen Phase 1 protocol numbers. Changing these invalidates comparability
 * across runs; any change requires re-running the whole study.
 */
data class BenchmarkConfig(
    val warmupCount: Int = 5,
    val measuredPasses: Int = 3,
    val batch: Int = 1,
)
