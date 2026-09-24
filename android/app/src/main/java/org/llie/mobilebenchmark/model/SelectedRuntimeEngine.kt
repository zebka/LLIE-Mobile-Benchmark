package org.llie.mobilebenchmark.model

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import java.io.File
import java.nio.FloatBuffer
import java.util.Collections

/**
 * The single runtime adapter selected by the Task 3 compatibility gate
 * (ONNX Runtime). The backend selects the execution provider: cpu
 * (CPUExecutionProvider), nnapi (NNAPI EP), xnnpack (XNNPACK EP), or the
 * schema labels gpu/npu which on this ORT build are only reachable via NNAPI.
 * Do not add a second unverified runtime adapter in Phase 1.
 */
class SelectedRuntimeEngine(private val backend: String = "cpu") : ModelEngine {

    private var env: OrtEnvironment? = null
    private var session: OrtSession? = null
    private var options: OrtSession.SessionOptions? = null
    private var manifest: ModelManifest? = null

    override fun load(modelFile: File, manifest: ModelManifest) {
        close()
        val environment = OrtEnvironment.getEnvironment()
        val sessionOptions = OrtSession.SessionOptions().apply {
            when (backend) {
                "cpu" -> addCPU(true)
                "nnapi", "gpu", "npu" -> addNnapi()
                "xnnpack" -> addXnnpack(emptyMap())
                else -> throw IllegalArgumentException("unsupported backend: $backend")
            }
        }
        val newSession = environment.createSession(modelFile.absolutePath, sessionOptions)
        env = environment
        session = newSession
        options = sessionOptions
        this.manifest = manifest
    }

    override fun infer(input: RgbImage): RgbImage {
        val m = checkNotNull(manifest) { "engine not loaded" }
        val session = checkNotNull(session)
        val environment = checkNotNull(env)

        require(input.width == m.inputWidth && input.height == m.inputHeight) {
            "input ${input.width}x${input.height} does not match manifest ${m.inputWidth}x${m.inputHeight}"
        }

        val h = m.inputHeight
        val w = m.inputWidth
        // RgbImage holds interleaved RGB (HWC); the graph expects NCHW.
        val chw = FloatArray(3 * h * w)
        var src = 0
        for (y in 0 until h) {
            for (x in 0 until w) {
                val r = input.data[src]
                val g = input.data[src + 1]
                val b = input.data[src + 2]
                src += 3
                val plane = y * w + x
                chw[plane] = r
                chw[h * w + plane] = g
                chw[2 * h * w + plane] = b
            }
        }
        val shape = longArrayOf(1, 3, h.toLong(), w.toLong())
        OnnxTensor.createTensor(environment, FloatBuffer.wrap(chw), shape).use { tensor ->
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
        options?.close()
        options = null
        env = null
        manifest = null
    }
}