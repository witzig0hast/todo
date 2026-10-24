package app.todo.client

import android.app.Activity
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.FileProvider
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest

/**
 * App-Updates über den eigenen Server: Die CI (oder ein Admin) lädt die APK hoch, die App fragt höchstens alle
 * 6 Stunden nach (GET /api/app/android), meldet eine neuere Version und installiert sie nach Bestätigung.
 * Updates funktionieren nur, wenn alle Versionen mit demselben Schlüssel signiert sind (siehe android/README.md).
 */
object Updater {
    private const val NOTIFICATION_ID = 9000
    private const val INTERVAL_MS = 6 * 60 * 60 * 1000L

    fun available(context: Context): JSONObject? {
        val raw = Prefs(context).updateInfo
        if (raw.isBlank()) return null
        val info = try { JSONObject(raw) } catch (_: Exception) { return null }
        return if (info.optInt("version_code") > BuildConfig.VERSION_CODE) info else null
    }

    fun checkAsync(context: Context, force: Boolean = false) {
        val app = context.applicationContext
        Thread { check(app, force) }.start()
    }

    private fun check(context: Context, force: Boolean) {
        val prefs = Prefs(context)
        val server = prefs.serverUrl ?: return
        val token = prefs.deviceToken ?: return
        if (!force && System.currentTimeMillis() - prefs.lastUpdateCheck < INTERVAL_MS) return
        val body = Http.get("$server/api/app/android", token) ?: return
        prefs.lastUpdateCheck = System.currentTimeMillis()
        val info = try { JSONObject(body) } catch (_: Exception) { return }
        val code = info.optInt("version_code")
        if (!info.optBoolean("available") || code <= BuildConfig.VERSION_CODE) {
            prefs.updateInfo = ""
            return
        }
        prefs.updateInfo = info.toString()
        if (prefs.notifiedUpdate == code || !Notifier.allowed(context)) return
        prefs.notifiedUpdate = code
        val open = Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            .putExtra(MainActivity.EXTRA_UPDATE, true)
        val pi = PendingIntent.getActivity(context, NOTIFICATION_ID, open, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val n = NotificationCompat.Builder(context, Notifier.CHANNEL_MESSAGES)
            .setSmallIcon(R.drawable.ic_stat_check)
            .setContentTitle("Update verfügbar: ${info.optString("version_name")}")
            .setContentText("Installiert ist ${BuildConfig.VERSION_NAME}. Tippen zum Aktualisieren.")
            .setContentIntent(pi)
            .setAutoCancel(true)
            .build()
        try {
            NotificationManagerCompat.from(context).notify(NOTIFICATION_ID, n)
        } catch (_: SecurityException) {
        }
    }

    /** Fragt nach, lädt die APK, prüft die Prüfsumme und startet die Android-Installation. */
    fun install(activity: Activity) {
        val info = available(activity)
        if (info == null) {
            Toast.makeText(activity, "Die App ist aktuell.", Toast.LENGTH_SHORT).show()
            checkAsync(activity, force = true)
            return
        }
        if (Build.VERSION.SDK_INT >= 26 && !activity.packageManager.canRequestPackageInstalls()) {
            Toast.makeText(activity, "Bitte „Unbekannte Apps installieren“ für Todo erlauben und erneut tippen.", Toast.LENGTH_LONG).show()
            try {
                activity.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${activity.packageName}")))
            } catch (_: Exception) {
            }
            return
        }
        AlertDialog.Builder(activity)
            .setTitle("Update auf ${info.optString("version_name")}")
            .setMessage("Installiert ist ${BuildConfig.VERSION_NAME}. Jetzt herunterladen (${info.optLong("size") / 1024 / 1024 + 1} MB) und installieren?")
            .setPositiveButton("Aktualisieren") { _, _ -> download(activity, info) }
            .setNegativeButton("Später", null)
            .show()
    }

    private fun download(activity: Activity, info: JSONObject) {
        val prefs = Prefs(activity)
        val server = prefs.serverUrl ?: return
        val token = prefs.deviceToken ?: return
        val progress = AlertDialog.Builder(activity).setMessage("Update wird geladen …").setCancelable(false).show()
        Thread {
            val file = File(activity.cacheDir, "updates/todo-update.apk")
            val ok = Http.download("$server/api/app/android/download", token, file) && sha256(file) == info.optString("sha256")
            activity.runOnUiThread {
                progress.dismiss()
                if (!ok) {
                    Toast.makeText(activity, "Download fehlgeschlagen oder Datei beschädigt.", Toast.LENGTH_LONG).show()
                    return@runOnUiThread
                }
                val uri = FileProvider.getUriForFile(activity, "${activity.packageName}.files", file)
                val intent = Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/vnd.android.package-archive")
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
                try {
                    activity.startActivity(intent)
                } catch (_: Exception) {
                    Toast.makeText(activity, "Installation konnte nicht gestartet werden.", Toast.LENGTH_LONG).show()
                }
            }
        }.start()
    }

    private fun sha256(file: File): String {
        val md = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buf = ByteArray(64 * 1024)
            while (true) {
                val n = input.read(buf)
                if (n < 0) break
                md.update(buf, 0, n)
            }
        }
        return md.digest().joinToString("") { "%02x".format(it) }
    }
}
