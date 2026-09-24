package org.llie.mobilebenchmark

import android.content.Intent
import android.os.Bundle
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import org.llie.mobilebenchmark.runner.BenchmarkExecutor
import java.io.File

/**
 * Entry point and run host.
 *
 * - Launcher (no action): lists the staged artifacts for the smoke test.
 * - Action ACTION_RUN: starts one on-device batch run on a worker thread.
 *   Timing lives entirely inside BenchmarkRunner (SystemClock monotonic);
 *   this activity never times anything across ADB.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var status: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 48, 48, 48)
        }
        status = TextView(this).apply {
            text = describeArtifacts()
            textSize = 16f
        }
        root.addView(status)
        setContentView(root)
        handleIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    private fun handleIntent(intent: Intent?) {
        if (intent?.action != ACTION_RUN) return
        val modelId = intent.getStringExtra(EXTRA_MODEL_ID)
        if (modelId.isNullOrEmpty()) {
            status.text = "missing model_id extra"
            return
        }
        val imageSet = intent.getStringExtra(EXTRA_IMAGE_SET) ?: "eval15"
        val backend = intent.getStringExtra(EXTRA_BACKEND)?.takeIf { it.isNotBlank() } ?: "cpu"
        synchronized(runningLock) {
            if (isRunning) {
                status.text = "already running"
                return
            }
            isRunning = true
        }
        status.text = "running $modelId/$backend on $imageSet ..."
        Thread {
            val outcome = try {
                BenchmarkExecutor(applicationContext).run(modelId, imageSet, backend)
            } catch (t: Throwable) {
                BenchmarkExecutor.RunOutcome(false, File(filesDir, "$modelId-run.json"), t.toString())
            }
            runOnUiThread {
                synchronized(runningLock) { isRunning = false }
                status.text = if (outcome.success) {
                    "done: ${outcome.resultFile.name}"
                } else {
                    "failed: ${outcome.detail}"
                }
            }
        }.start()
    }

    private fun describeArtifacts(): String {
        val dir = getExternalFilesDir(null)
        val models = dir?.listFiles { f -> f.isFile && f.extension == "onnx" }.orEmpty()
        return buildString {
            append("LLIE Benchmark ready\n")
            append("models dir: ").append(dir?.absolutePath).append('\n')
            append("artifacts: ").append(models.size).append('\n')
            models.forEach { append(" - ").append(it.name).append('\n') }
        }
    }

    companion object {
        const val ACTION_RUN = "org.llie.bench.RUN"
        const val EXTRA_MODEL_ID = "model_id"
        const val EXTRA_IMAGE_SET = "image_set"
        const val EXTRA_BACKEND = "backend"
        private val runningLock = Any()
        @Volatile private var isRunning = false
    }
}
