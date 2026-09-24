package org.llie.mobilebenchmark.model

import android.graphics.Bitmap
import android.graphics.BitmapFactory

/** Bitmap <-> RgbImage conversion at the manifest's input contract. */
object ImageCodec {

    fun decodeFile(path: String): Bitmap =
        BitmapFactory.decodeFile(path) ?: throw IllegalStateException("cannot decode $path")

    fun fromBitmap(bitmap: Bitmap): RgbImage {
        val width = bitmap.width
        val height = bitmap.height
        val pixels = IntArray(width * height)
        bitmap.getPixels(pixels, 0, width, 0, 0, width, height)
        val data = FloatArray(width * height * 3)
        var i = 0
        for (p in pixels) {
            data[i++] = ((p shr 16) and 0xFF) / 255f
            data[i++] = ((p shr 8) and 0xFF) / 255f
            data[i++] = (p and 0xFF) / 255f
        }
        return RgbImage(width, height, data)
    }

    fun savePng(image: RgbImage, path: String) {
        val pixels = IntArray(image.width * image.height)
        var i = 0
        for (p in pixels.indices) {
            val r = (image.data[i++] * 255f).coerceIn(0f, 255f).toInt()
            val g = (image.data[i++] * 255f).coerceIn(0f, 255f).toInt()
            val b = (image.data[i++] * 255f).coerceIn(0f, 255f).toInt()
            pixels[p] = (0xFF shl 24) or (r shl 16) or (g shl 8) or b
        }
        val bitmap = Bitmap.createBitmap(image.width, image.height, Bitmap.Config.ARGB_8888)
        bitmap.setPixels(pixels, 0, image.width, 0, 0, image.width, image.height)
        val file = java.io.File(path)
        file.parentFile?.mkdirs()
        file.outputStream().use { stream ->
            bitmap.compress(Bitmap.CompressFormat.PNG, 100, stream)
        }
        // World-readable so host `adb pull` works when the file is app-created.
        file.setReadable(true, false)
        bitmap.recycle()
    }
}
