package app.todo.client

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import android.webkit.WebView
import androidx.webkit.JavaScriptReplyProxy
import androidx.webkit.WebMessageCompat
import androidx.webkit.WebViewCompat
import org.json.JSONObject

/**
 * Schnittstelle zwischen der Web-Oberfläche und der App (`window.TodoAndroid`). Wird nur für die eigene Server-Origin
 * eingebunden (allowedOriginRules) und nur vom Hauptframe beantwortet.
 */
class Bridge(private val activity: MainActivity, private val prefs: Prefs) : WebViewCompat.WebMessageListener {

    override fun onPostMessage(
        view: WebView,
        message: WebMessageCompat,
        sourceOrigin: Uri,
        isMainFrame: Boolean,
        replyProxy: JavaScriptReplyProxy,
    ) {
        if (!isMainFrame) return
        val json = try { JSONObject(message.data ?: return) } catch (e: Exception) { return }
        when (json.optString("type")) {
            "hello" -> replyProxy.postMessage(info().toString())
            "register" -> register(json, replyProxy)
            "unregister" -> {
                prefs.clearDevice()
                PushService.stop(activity)
            }
            "openNotificationSettings" -> startSafely(
                Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, activity.packageName)
            )
            "setAppLock" -> activity.setAppLock(json.optBoolean("enabled", false))
            "enableLocation" -> activity.requestLocationForReminders()
            "widgetRefresh" -> TodoWidget.refresh(activity)
            "installUpdate" -> Updater.install(activity)
            "openBatterySettings" -> startSafely(
                Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:${activity.packageName}"))
            )
        }
    }

    private fun info(): JSONObject {
        val pm = activity.getSystemService(PowerManager::class.java)
        return JSONObject()
            .put("type", "info")
            .put("name", deviceName())
            .put("model", Build.MODEL)
            .put("appVersion", BuildConfig.VERSION_NAME)
            .put("registered", prefs.deviceToken != null)
            .put("deviceId", prefs.deviceId)
            .put("notificationsAllowed", Notifier.allowed(activity))
            .put("connected", PushService.connected)
            .put("batteryUnrestricted", pm.isIgnoringBatteryOptimizations(activity.packageName))
            .put("appLock", prefs.appLock)
            .put("locationAllowed", Geofences.allowed(activity))
            .put("update", Updater.available(activity)?.optString("version_name") ?: JSONObject.NULL)
    }

    private fun register(json: JSONObject, reply: JavaScriptReplyProxy) {
        val token = json.optString("token")
        val id = json.optInt("deviceId", -1)
        val server = Prefs.normalizeServerUrl(json.optString("serverUrl"))
        // Nur für den konfigurierten Server akzeptieren
        if (token.isBlank() || id < 0 || server == null || server != prefs.serverUrl) return
        prefs.deviceToken = token
        prefs.deviceId = id
        prefs.deviceName = json.optString("name").ifBlank { deviceName() }
        PushService.start(activity)
        reply.postMessage(JSONObject().put("type", "registered").put("deviceId", id).toString())
    }

    private fun deviceName(): String {
        val custom = try { Settings.Global.getString(activity.contentResolver, "device_name") } catch (e: Exception) { null }
        return custom?.takeIf { it.isNotBlank() } ?: Build.MODEL
    }

    private fun startSafely(intent: Intent) {
        try {
            activity.startActivity(intent)
        } catch (e: Exception) {
            try {
                activity.startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
            } catch (_: Exception) {
            }
        }
    }
}
