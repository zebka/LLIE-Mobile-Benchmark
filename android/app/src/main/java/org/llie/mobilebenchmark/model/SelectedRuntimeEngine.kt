package org.llie.mobilebenchmark.model

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import java.io.File
import java.nio.FloatBuffer
import java.util.Collections

/**
 * The single runtime adapter selected by the Task 3 compatibility gate
 * (ONNX Runtime, CPU execution provider). Do not add a second unverified
 * runtime adapter in Phase 1.
 */
class SelectedRuntimeEngine : ModelEngine {

    private var env: OrtEnvironment? = null
    private var session: OrtSession? = null
    private var manifest: ModelManifest? = null

    override fun load(modelFile: File, manifest: ModelManifest) {
        close()
        val environment = OrtEnvironment.getEnvironment()
        val options = OrtSession.SessionOptions().apply {
            addCPU(true)
        }
        val newSession = environment.createSession(modelFile.absolutePath, options)
        env = environment
        session = newSession
        this.manifest = manifest
    }

    override fun infer(input: RgbImage): RgbImage {
        val m = checkNotNull(manifest) { "engine not loaded" }
        val session = checkNotNull(session)
        val environment = checkNotNull(env)

        require(input.width == m.inputWidth && input.height == m.inputHeight) {
            "input ${input.width}x${input.height} does not match manifest ${m.inputWidth}x${m.inputHeight}"
        }

        val shape = longArrayOf(1, 3, m.inputHeight.toLong(), m.inputWidth.toLong())
        OnnxTensor.createTensor(environment, FloatBuffer.wrap(input.data), shape).use { tensor ->
            session.run(Collections.singletonMap("input", tensor)).use { results ->
                @Suppress("UNCHECKED_CAST")
                val output = results.get(0).value as Array<Array<Array<FloatArray>>>
                val out = RgbImage.zeros(m.outputWidth, m.outputHeight)
                // NCHW -> interleaved RGB
                val oh = m.outputHeight
                val ow = m.outputWidth
                var i = 0
                for (y in 0 until oh) {
                    for (x in 0 until ow) {
                        out.data[i++] = output[0][0][y][x]
                        out.data[i++] = output[0][1][y][x]
                        out.data[i++] = output[0][2][y][x]
                    }
                }
                return out
            }
        }
    }

    override fun close() {
        session?.close()
        session = null
        env = null
        manifest = null
    }
}