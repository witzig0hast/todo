package app.todo.client

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/** Gemeinsamer HTTP-Client für kurze Aufrufe (Aktionen, Orte). */
object Http {
    val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    private val JSON_TYPE = "application/json".toMediaType()

    /** POST mit JSON-Körper. Gibt true bei 2xx zurück. */
    fun postJson(url: String, body: JSONObject, bearer: String? = null): Boolean {
        val builder = Request.Builder().url(url).post(body.toString().toRequestBody(JSON_TYPE))
        if (bearer != null) builder.header("Authorization", "Bearer $bearer")
        return try {
            client.newCall(builder.build()).execute().use { it.isSuccessful }
        } catch (e: IOException) {
            false
        }
    }

    /** POST mit JSON-Körper, gibt (HTTP-Status, Antworttext) zurück; Status 0 = keine Verbindung. */
    fun postJsonResult(url: String, body: JSONObject, bearer: String?): Pair<Int, String?> {
        val builder = Request.Builder().url(url).post(body.toString().toRequestBody(JSON_TYPE))
        if (bearer != null) builder.header("Authorization", "Bearer $bearer")
        return try {
            client.newCall(builder.build()).execute().use { it.code to it.body?.string() }
        } catch (e: IOException) {
            0 to null
        }
    }

    /** Lädt eine Datei herunter (z. B. App-Update). Gibt true bei Erfolg zurück. */
    fun download(url: String, bearer: String?, target: java.io.File): Boolean {
        val builder = Request.Builder().url(url).get()
        if (bearer != null) builder.header("Authorization", "Bearer $bearer")
        return try {
            client.newBuilder().readTimeout(120, TimeUnit.SECONDS).build().newCall(builder.build()).execute().use { r ->
                val body = r.body
                if (!r.isSuccessful || body == null) return false
                target.parentFile?.mkdirs()
                target.outputStream().use { out -> body.byteStream().copyTo(out) }
                true
            }
        } catch (e: IOException) {
            false
        }
    }

    /** GET, gibt den Text bei 2xx zurück, sonst null. Bei 401 wird [onUnauthorized] aufgerufen. */
    fun get(url: String, bearer: String?, onUnauthorized: () -> Unit = {}): String? {
        val builder = Request.Builder().url(url).get()
        if (bearer != null) builder.header("Authorization", "Bearer $bearer")
        return try {
            client.newCall(builder.build()).execute().use { r ->
                if (r.code == 401) { onUnauthorized(); null } else if (r.isSuccessful) r.body?.string() else null
            }
        } catch (e: IOException) {
            null
        }
    }
}
