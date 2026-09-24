package org.llie.mobilebenchmark.storage

import org.json.JSONArray
import org.json.JSONObject
import org.llie.mobilebenchmark.runner.ImageRunResult
import java.io.File

/** Writes the stable, schema-shaped run-result JSON for one model run. */
object ResultWriter {

    fun resultJson(
        modelId: String,
        artifactSha256: String,
        deviceModel: String,
        androidRelease: String,
        androidSdk: Int,
        buildFingerprint: String,
        soc: String,
        runtimeName: String,
        runtimeVersion: String,
        backend: String,
        precision: String,
        warmupCount: Int,
        loadTimeNs: Long,
        results: List<ImageRunResult>,
        outputPaths: Map<String, String>,
        pssSamplesMb: List<Double>,
        thermalBefore: String,
        thermalAfter: String,
        runFailureReason: String = "",
    ): JSONObject {
        val images = JSONArray()
        val imageIds = JSONArray()
        val paths = JSONArray()
        for (r in results) {
            imageIds.put(r.imageId)
            if (r.success) {
                outputPaths[r.imageId]?.let { paths.put(it) }
            }
            images.put(
                JSONObject()
                    .put("image_id", r.imageId)
                    .put("model_ns", JSONArray(r.modelNs))
                    .put("e2e_ns", JSONArray(r.e2eNs))
            )
        }
        val firstFailedReason = results.firstOrNull { !it.success }?.failureReason ?: ""
        val success = results.isNotEmpty() && results.all { it.success }
        val failureReason = firstFailedReason.ifEmpty { runFailureReason }.ifEmpty { "run failed" }
        val peakMb = pssSamplesMb.maxOrNull() ?: 0.0

        return JSONObject()
            .put("model_id", modelId)
            .put("artifact_sha256", artifactSha256)
            .put(
                "device",
                JSONObject()
                    .put("model", deviceModel)
                    .put("android_release", androidRelease)
                    .put("android_sdk", androidSdk)
                    .put("build_fingerprint", buildFingerprint)
                    .put("soc", soc)
            )
            .put("runtime", JSONObject().put("name", runtimeName).put("version", runtimeVersion))
            .put("backend", backend)
            .put("precision", precision)
            .put("image_ids", imageIds)
            .put("warmup_count", warmupCount)
            .put("load_time_ns", loadTimeNs)
            .put("images", images)
            .put(
                "pss",
                JSONObject()
                    .put("samples_mb", JSONArray(pssSamplesMb))
                    .put("peak_mb", peakMb)
            )
            .put(
                "thermal",
                JSONObject().put("before", thermalBefore).put("after", thermalAfter)
            )
            .put("output_paths", paths)
            .put("success", success)
            .apply { if (!success) put("failure_reason", failureReason) }
    }

    fun write(file: File, payload: JSONObject) {
        file.parentFile?.mkdirs()
        file.writeText(payload.toString(2), Charsets.UTF_8)
    }
}
