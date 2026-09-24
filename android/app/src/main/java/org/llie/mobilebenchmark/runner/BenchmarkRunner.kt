package org.llie.mobilebenchmark.runner

import android.os.SystemClock
import org.llie.mobilebenchmark.model.ModelEngine
import org.llie.mobilebenchmark.model.ModelManifest
import org.llie.mobilebenchmark.model.RgbImage
import java.io.File

/**
 * Owns the Phase 1 run protocol: batch=1, warm-up passes, then
 * `config.measuredPasses` measured passes per image with an in-process
 * monotonic clock (`SystemClock.elapsedRealtimeNanos`).
 */
class BenchmarkRunner(
    private val engine: ModelEngine,
    private val config: BenchmarkConfig = BenchmarkConfig(),
    private val clock: () -> Long = { SystemClock.elapsedRealtimeNanos() },
) {

    data class Loaded(val manifest: ModelManifest, val loadTimeNs: Long)

    fun load(modelFile: File, manifestText: String): Loaded {
        val manifest = ModelManifest.fromJson(manifestText)
        val start = clock()
        engine.load(modelFile, manifest)
        val loadTime = clock() - start
        return Loaded(manifest, loadTime)
    }

    fun warmup(manifest: ModelManifest, image: RgbImage) {
        repeat(config.warmupCount) { engine.infer(image) }
    }

    fun measure(imageId: String, image: RgbImage): ImageRunResult {
        val modelSamples = ArrayList<Long>(config.measuredPasses)
        val e2eSamples = ArrayList<Long>(config.measuredPasses)
        var lastOutput: RgbImage? = null

        for (pass in 0 until config.measuredPasses) {
            val e2eStart = clock()
            val modelStart = clock()
            val output = try {
                engine.infer(image)
            } catch (t: Throwable) {
                return ImageRunResult(
                    imageId = imageId,
                    modelNs = modelSamples,
                    e2eNs = e2eSamples,
                    output = null,
                    success = false,
                    failureReason = "${t.javaClass.simpleName}: ${t.message}",
                )
            }
            val modelEnd = clock()
            val e2eEnd = clock()
            modelSamples.add(modelEnd - modelStart)
            e2eSamples.add(e2eEnd - e2eStart)
            lastOutput = output
        }
        return ImageRunResult(imageId, modelSamples, e2eSamples, lastOutput, success = true, failureReason = "")
    }
}