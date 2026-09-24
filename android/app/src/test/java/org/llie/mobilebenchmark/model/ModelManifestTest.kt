package org.llie.mobilebenchmark.model

import org.json.JSONException
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class ModelManifestTest {

    private val valid = """
        {
          "model_id": "zero-dce",
          "artifact": "zero-dce.onnx",
          "precision": "float32",
          "input": {"width": 64, "height": 96},
          "output": {"width": 64, "height": 96},
          "preprocessing": {"steps": ["normalize_0_1"]},
          "channel_order": "RGB",
          "input_range": [0.0, 1.0],
          "tensor_layout": "NCHW",
          "output_range": [0.0, 1.0],
          "tiling": {"tile_width": 512, "tile_height": 512, "overlap": 32}
        }
    """.trimIndent()

    @Test
    fun parsesValidManifest() {
        val m = ModelManifest.fromJson(valid)
        assertEquals("zero-dce", m.modelId)
        assertEquals(64, m.inputWidth)
        assertEquals(96, m.inputHeight)
        assertEquals("NCHW", m.tensorLayout)
        assertEquals(0.0f, m.inputRangeMin)
        assertEquals(1.0f, m.outputRangeMax)
    }

    @Test
    fun rejectsMissingModelId() {
        val broken = valid.replace("\"model_id\": \"zero-dce\",", "")
        assertThrows(JSONException::class.java) { ModelManifest.fromJson(broken) }
    }

    @Test
    fun rejectsMissingInputBlock() {
        val broken = valid.replace("\"input\": {\"width\": 64, \"height\": 96},", "")
        assertThrows(JSONException::class.java) { ModelManifest.fromJson(broken) }
    }
}
