package org.llie.mobilebenchmark

import android.os.Bundle
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import java.io.File

/**
 * Phase 1 entry point. The full UI (model/backend/image-set selection) is
 * completed in later plan steps; this activity currently lists the model
 * artifacts found in the app-specific external files directory so the
 * smoke test in the plan can verify install + launch without ADB timing.
 */
class MainActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 48, 48, 48)
        }
        val status = TextView(this).apply {
            text = describeArtifacts()
            textSize = 16f
        }
        root.addView(status)
        setContentView(root)
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
        fun defaultModelsDir(): File = throw UnsupportedOperationException("provided by activity context")
    }
}