package org.llie.mobilebenchmark.model

import org.json.JSONObject

/**
 * Parsed view of `protocol/model-manifest.schema.json`.
 * Only the fields the runner needs are extracted; unknown keys are ignored.
 */
data class ModelManifest(
    val modelId: String,
    val artifact: String,
    val tensorLayout: String,
    val channelOrder: String,
    val inputWidth: Int,
    val inputHeight: Int,
    val outputWidth: Int,
    val outputHeight: Int,
    val inputRangeMin: Float,
    val inputRangeMax: Float,
    val outputRangeMin: Float,
    val outputRangeMax: Float,
) {
    companion object {
        fun fromJson(text: String): ModelManifest {
            val obj = JSONObject(text)
            val input = obj.getJSONObject("input")
            val output = obj.getJSONObject("output")
            val inputRange = obj.getJSONArray("input_range")
            val outputRange = obj.getJSONArray("output_range")
            return ModelManifest(
                modelId = obj.getString("model_id"),
                artifact = obj.getString("artifact"),
                tensorLayout = obj.getString("tensor_layout"),
                channelOrder = obj.getString("channel_order"),
                inputWidth = input.getInt("width"),
                inputHeight = input.getInt("height"),
                outputWidth = output.getInt("width"),
                outputHeight = output.getInt("height"),
                inputRangeMin = inputRange.getDouble(0).toFloat(),
                inputRangeMax = inputRange.getDouble(1).toFloat(),
                outputRangeMin = outputRange.getDouble(0).toFloat(),
                outputRangeMax = outputRange.getDouble(1).toFloat(),
            )
        }
    }
}