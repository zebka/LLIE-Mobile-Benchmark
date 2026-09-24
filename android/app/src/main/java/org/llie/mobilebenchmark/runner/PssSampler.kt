package org.llie.mobilebenchmark.runner

import java.io.File

/**
 * Samples this process's PSS from /proc/self/smaps_rollup while a run is in
 * progress. Own-process smaps_rollup is readable without extra permissions.
 */
class PssSampler(private val intervalMs: Long = 500) {

    private val samplesMb = mutableListOf<Double>()
    private var thread: Thread? = null
    @Volatile private var running = false

    @Synchronized
    fun start() {
        if (running) return
        running = true
        samplesMb.clear()
        thread = Thread {
            while (running) {
                readPssMb()?.let { value ->
                    synchronized(samplesMb) { samplesMb.add(value) }
                }
                try {
                    Thread.sleep(intervalMs)
                } catch (e: InterruptedException) {
                    break
                }
            }
        }.apply { isDaemon = true; start() }
    }

    @Synchronized
    fun stop(): List<Double> {
        running = false
        thread?.join(1000)
        thread = null
        synchronized(samplesMb) { return samplesMb.toList() }
    }

    companion object {
        fun readPssMb(): Double? = try {
            var pss: Double? = null
            File("/proc/self/smaps_rollup").forEachLine { line ->
                if (pss == null && line.startsWith("Pss:")) {
                    val parts = line.trim().split(Regex("\\s+"))
                    if (parts.size >= 2) {
                        pss = parts[1].toDouble() / 1024.0
                    }
                }
            }
            pss
        } catch (e: Throwable) {
            null
        }
    }
}
