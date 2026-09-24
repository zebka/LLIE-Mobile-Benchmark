package org.llie.mobilebenchmark.runner

import org.llie.mobilebenchmark.model.RgbImage

/** One image's measurement record; success/failure is explicit, never silent. */
data class ImageRunResult(
    val imageId: String,
    val modelNs: List<Long>,
    val e2eNs: List<Long>,
    val output: RgbImage?,
    val success: Boolean,
    val failureReason: String,
)
