package app.todo.client

import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.ConnectivityManager
import android.net.Network
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Hält eine dauerhafte SSE-Verbindung zum Todo-Server (`/api/devices/stream`, Geräte-Token) und zeigt jede Nachricht
 * als Benachrichtigung. Nachrichten, die während einer Offline-Zeit anfielen, liefert der Server beim Verbinden nach.
 * Kein Google-Dienst (FCM) nötig.
 */
class PushService : Service() {
    private val lock = Object()
    @Volatile private var running = false
    private var worker: Thread? = null
    private var networkCallback: ConnectivityManager.NetworkCallback? = null

    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS) // der Server sendet alle 20 s einen Ping
        .retryOnConnectionFailure(true)
        .build()

    override fun onCreate() {
        super.onCreate()
        Notifier.ensureChannels(this)
        enterForeground()
        registerNetworkCallback()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (worker == null) {
            running = true
            worker = Thread({ loop() }, "todo-push").also { it.isDaemon = true; it.start() }
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        running = false
        connected = false
        networkCallback?.let {
            try { getSystemService(ConnectivityManager::class.java).unregisterNetworkCallback(it) } catch (_: Exception) {}
        }
        worker?.interrupt()
        worker = null
        super.onDestroy()
    }

    private fun enterForeground() {
        val notification = NotificationCompat.Builder(this, Notifier.CHANNEL_SERVICE)
            .setSmallIcon(R.drawable.ic_stat_check)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(getString(R.string.service_text))
            .setOngoing(true)
            .setSilent(true)
            .setPriority(NotificationCompat.PRIORITY_MIN)
            .setContentIntent(Notifier.openAppIntent(this, 0, null))
            .build()
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(FOREGROUND_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        } else {
            startForeground(FOREGROUND_ID, notification)
        }
    }

    private fun registerNetworkCallback() {
        val cm = getSystemService(ConnectivityManager::class.java)
        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                // Netz ist wieder da: nicht auf die nächste Wartezeit warten, sofort neu verbinden
                synchronized(lock) { lock.notifyAll() }
            }
        }
        try {
            cm.registerDefaultNetworkCallback(callback)
            networkCallback = callback
        } catch (_: Exception) {
        }
    }

    private fun loop() {
        val prefs = Prefs(this)
        var backoff = 2_000L
        while (running) {
            val token = prefs.deviceToken
            val server = prefs.serverUrl
            if (token == null || server == null) {
                shutdown()
                return
            }
            try {
                val request = Request.Builder()
                    .url("$server/api/devices/stream")
                    .header("Authorization", "Bearer $token")
                    .header("Accept", "text/event-stream")
                    .build()
                client.newCall(request).execute().use { response ->
                    if (response.code == 401) {
                        // Gerät wurde auf dem Server entfernt: lokal abmelden, die Web-Oberfläche registriert neu
                        prefs.clearDevice()
                        shutdown()
                        return
                    }
                    if (!response.isSuccessful) throw IOException("HTTP ${response.code}")
                    connected = true
                    backoff = 2_000L
                    readStream(response.body!!.source(), token, server)
                }
            } catch (e: IOException) {
                // Verbindung verloren -> neu verbinden
            } catch (e: InterruptedException) {
                return
            }
            connected = false
            if (!running) return
            try {
                synchronized(lock) { lock.wait(backoff) }
            } catch (e: InterruptedException) {
                return
            }
            backoff = minOf(backoff * 2, 60_000L)
        }
    }

    private fun readStream(source: okio.BufferedSource, token: String, server: String) {
        var event = ""
        val data = StringBuilder()
        while (running) {
            val line = source.readUtf8Line() ?: return // Ende des Streams
            when {
                line.isEmpty() -> {
                    if (event == "message" && data.isNotEmpty()) handleMessage(data.toString(), token, server)
                    event = ""
                    data.setLength(0)
                }
                line.startsWith(":") -> Unit // Kommentar/Ping
                line.startsWith("event:") -> event = line.substring(6).trim()
                line.startsWith("data:") -> {
                    if (data.isNotEmpty()) data.append('\n')
                    data.append(line.substring(5).trimStart())
                }
            }
        }
    }

    private fun handleMessage(json: String, token: String, server: String) {
        val msg = try { JSONObject(json) } catch (e: Exception) { return }
        val id = msg.optInt("id", -1)
        if (id < 0) return
        val url = msg.optString("url").takeIf { it.startsWith("/") && !it.startsWith("//") }
        val shown = Notifier.show(this, id, msg.optString("title", "Todo"), msg.optString("body", ""), url)
        if (!shown) return // Benachrichtigungen aus: nicht bestätigen, der Server liefert später erneut
        try {
            val ack = Request.Builder()
                .url("$server/api/devices/messages/$id/ack")
                .header("Authorization", "Bearer $token")
                .post(ByteArray(0).toRequestBody(null))
                .build()
            client.newCall(ack).execute().close()
        } catch (_: IOException) {
            // wird beim nächsten Verbinden erneut zugestellt (gleiche Benachrichtigungs-ID ersetzt die alte)
        }
    }

    private fun shutdown() {
        connected = false
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    companion object {
        private const val FOREGROUND_ID = 1
        @Volatile var connected = false

        fun start(context: Context) {
            ContextCompat.startForegroundService(context, Intent(context, PushService::class.java))
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, PushService::class.java))
        }
    }
}
