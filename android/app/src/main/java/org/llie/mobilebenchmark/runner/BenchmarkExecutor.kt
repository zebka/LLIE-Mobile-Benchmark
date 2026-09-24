package org.llie.mobilebenchmark.runner

import android.content.Context
import android.os.Build
import android.os.PowerManager
import org.json.JSONObject
import org.llie.mobilebenchmark.model.ImageCodec
import org.llie.mobilebenchmark.model.RgbImage
import org.llie.mobilebenchmark.model.SelectedRuntimeEngine
import org.llie.mobilebenchmark.storage.ResultWriter
import java.io.File
import java.security.MessageDigest

/**
 * One end-to-end on-device run: load model, warm up + measure per image,
 * save outputs, and write a schema-shaped run-result JSON. All timing uses
 * the in-process monotonic clock inside BenchmarkRunner; nothing here crosses
 * the ADB boundary while measuring.
 */
class BenchmarkExecutor(
    private val context: Context,
    private val config: BenchmarkConfig = BenchmarkConfig(),
    private val clock: () -> Long = { android.os.SystemClock.elapsedRealtimeNanos() },
) {

    data class RunOutcome(val success: Boolean, val resultFile: File, val detail: String)

    fun run(modelId: String, imageSet: String, backend: String = "cpu"): RunOutcome {
        val base = context.getExternalFilesDir(null)
            ?: return RunOutcome(false, File(context.filesDir, "$modelId-run.json"), "no external files dir")
        val resultsDir = File(base, "results")
        val outputsDir = File(resultsDir, "outputs")
        val suffix = if (backend == "cpu") "" else "-$backend"
        val resultFile = File(resultsDir, "$modelId$suffix-run.json")
        val statusFile = File(resultsDir, "$modelId$suffix.status")
        statusFile.parentFile?.mkdirs()
        statusFile.writeText("running")

        val thermalBefore = thermalStatus(context)
        val sampler = PssSampler()
        sampler.start()

        val engine = SelectedRuntimeEngine(backend)
        val runner = BenchmarkRunner(engine, config, clock)
        val results = mutableListOf<ImageRunResult>()
        val outputPaths = mutableMapOf<String, String>()
        var loadTimeNs = 0L
        var failureReason = ""

        try {
            val manifestFile = File(base, "manifests/$modelId.manifest.json")
            val modelFile = File(base, "models/$modelId.onnx")
            if (!manifestFile.isFile) throw IllegalStateException("manifest missing: ${manifestFile.name}")
            if (!modelFile.isFile) throw IllegalStateException("model missing: ${modelFile.name}")

            val loaded = runner.load(modelFile, manifestFile.readText(Charsets.UTF_8))
            loadTimeNs = loaded.loadTimeNs
            val manifest = loaded.manifest

            val imagesDir = File(base, "images/$imageSet")
            val imageFiles = imagesDir.listFiles { f -> f.isFile && f.extension.equals("png", true) }
                ?.sortedBy { it.name }
                .orEmpty()
            if (imageFiles.isEmpty()) throw IllegalStateException("no images in $imageSet")

            for (file in imageFiles) {
                val bitmap = ImageCodec.decodeFile(file.absolutePath)
                if (bitmap.width != manifest.inputWidth || bitmap.height != manifest.inputHeight) {
                    results.add(
                        ImageRunResult(
                            imageId = file.name,
                            modelNs = emptyList(),
                            e2eNs = emptyList(),
                            output = null,
                            success = false,
                            failureReason = "shape mismatch: ${bitmap.width}x${bitmap.height} vs " +
                                "${manifest.inputWidth}x${manifest.inputHeight}",
                        )
                    )
                    bitmap.recycle()
                    continue
                }
                val rgb = ImageCodec.fromBitmap(bitmap)
                bitmap.recycle()
                runner.warmup(manifest, rgb)
                val measured = runner.measure(file.name, rgb)
                results.add(measured)
                if (measured.success) {
                    measured.output?.let { out ->
                        ImageCodec.savePng(out, File(outputsDir, file.name).absolutePath)
                        outputPaths[file.name] = "$outputsDirName/${file.name}"
                    }
                }
            }
        } catch (t: Throwable) {
            failureReason = "${t.javaClass.simpleName}: ${t.message}"
        } finally {
            engine.close()
        }

        val pssSamples = sampler.stop()
        val thermalAfter = thermalStatus(context)
        val payload = ResultWriter.resultJson(
            modelId = modelId,
            artifactSha256 = sha256Of(File(base, "models/$modelId.onnx")),
            deviceModel = Build.MODEL,
            androidRelease = Build.VERSION.RELEASE ?: "unknown",
            androidSdk = Build.VERSION.SDK_INT,
            buildFingerprint = Build.FINGERPRINT,
            soc = Build.SOC_MODEL ?: Build.BOARD,
            runtimeName = "onnxruntime",
            runtimeVersion = ortVersion(),
            backend = backend,
            precision = "float32",
            warmupCount = config.warmupCount,
            loadTimeNs = loadTimeNs,
            results = results,
            outputPaths = outputPaths,
            pssSamplesMb = pssSamples,
            thermalBefore = thermalBefore,
            thermalAfter = thermalAfter,
            runFailureReason = failureReason,
        )
        ResultWriter.write(resultFile, payload)
        val success = payload.optBoolean("success", false)
        statusFile.writeText(if (success) "done" else "failed")
        return RunOutcome(success, resultFile, payload.optString("failure_reason", ""))
    }

    companion object {
        fun sha256Of(file: File): String {
            if (!file.isFile) return "0".repeat(64)
            val digest = MessageDigest.getInstance("SHA-256")
            file.inputStream().use { input ->
                val buffer = ByteArray(8192)
                while (true) {
                    val read = input.read(buffer)
                    if (read <= 0) break
                    digest.update(buffer, 0, read)
                }
            }
            return digest.digest().joinToString("") { "%02x".format(it) }
        }

        fun thermalStatus(context: Context): String {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return "unavailable"
            val pm = context.getSystemService(Context.POWER_SERVICE) as? PowerManager
                ?: return "unavailable"
            return when (pm.currentThermalStatus) {
                PowerManager.THERMAL_STATUS_NONE -> "none"
                PowerManager.THERMAL_STATUS_LIGHT -> "light"
                PowerManager.THERMAL_STATUS_MODERATE -> "moderate"
                PowerManager.THERMAL_STATUS_SEVERE -> "severe"
                PowerManager.THERMAL_STATUS_CRITICAL -> "critical"
                PowerManager.THERMAL_STATUS_EMERGENCY -> "emergency"
                PowerManager.THERMAL_STATUS_SHUTDOWN -> "shutdown"
                else -> "unknown"
            }
        }

        fun ortVersion(): String = try {
            val envClass = Class.forName("ai.onnxruntime.OrtEnvironment")
            val getEnvironment = envClass.getMethod("getEnvironment")
            val env = getEnvironment.invoke(null)
            val versionMethod = envClass.methods.firstOrNull {
                it.name == "getVersion" && it.parameterCount == 0
            }
            versionMethod?.invoke(env)?.toString() ?: "unknown"
        } catch (t: Throwable) {
            "unknown"
        }
    }
}
