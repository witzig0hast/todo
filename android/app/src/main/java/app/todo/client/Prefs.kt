package app.todo.client

import android.content.Context
import java.net.URI

/** Einstellungen der App (nur im privaten App-Speicher, Backup ist ausgeschaltet). */
class Prefs(context: Context) {
    private val sp = context.applicationContext.getSharedPreferences("todo", Context.MODE_PRIVATE)

    var serverUrl: String?
        get() = sp.getString("server_url", null) ?: normalizeServerUrl(BuildConfig.DEFAULT_SERVER_URL)
        set(value) { sp.edit().putString("server_url", value).apply() }

    var deviceToken: String?
        get() = sp.getString("device_token", null)
        set(value) { sp.edit().putString("device_token", value).apply() }

    var deviceId: Int
        get() = sp.getInt("device_id", -1)
        set(value) { sp.edit().putInt("device_id", value).apply() }

    var deviceName: String?
        get() = sp.getString("device_name", null)
        set(value) { sp.edit().putString("device_name", value).apply() }

    /** Weitere Hosts, die im WebView geöffnet werden dürfen (z. B. der SSO-Anbieter, gelernt über Weiterleitungen). */
    var extraHosts: Set<String>
        get() = sp.getStringSet("extra_hosts", emptySet()) ?: emptySet()
        set(value) { sp.edit().putStringSet("extra_hosts", value).apply() }

    var appLock: Boolean
        get() = sp.getBoolean("app_lock", false)
        set(value) { sp.edit().putBoolean("app_lock", value).apply() }

    var geofenceIds: Set<Int>
        get() = (sp.getStringSet("geofence_ids", emptySet()) ?: emptySet()).mapNotNull { it.toIntOrNull() }.toSet()
        set(value) { sp.edit().putStringSet("geofence_ids", value.map { it.toString() }.toSet()).apply() }

    var geofenceData: String
        get() = sp.getString("geofence_data", "{}") ?: "{}"
        set(value) { sp.edit().putString("geofence_data", value).apply() }

    /** Letzte Widget-Daten (JSON), damit das Widget auch ohne Netz etwas zeigt. */
    var widgetData: String
        get() = sp.getString("widget_data", "{}") ?: "{}"
        set(value) { sp.edit().putString("widget_data", value).apply() }

    var lastUpdateCheck: Long
        get() = sp.getLong("last_update_check", 0L)
        set(value) { sp.edit().putLong("last_update_check", value).apply() }

    /** Zuletzt gemeldete neuere App-Version (JSON vom Server) oder leer. */
    var updateInfo: String
        get() = sp.getString("update_info", "") ?: ""
        set(value) { sp.edit().putString("update_info", value).apply() }

    var notifiedUpdate: Int
        get() = sp.getInt("notified_update", 0)
        set(value) { sp.edit().putInt("notified_update", value).apply() }

    fun clearDevice() {
        sp.edit().remove("device_token").remove("device_id").remove("device_name").remove("widget_data").apply()
    }

    companion object {
        /** Gibt "https://host[:port]" zurück oder null, wenn die Eingabe keine gültige https-Adresse ist. */
        fun normalizeServerUrl(input: String?): String? {
            val raw = input?.trim().orEmpty()
            if (raw.isEmpty()) return null
            val withScheme = if (raw.contains("://")) raw else "https://$raw"
            return try {
                val uri = URI(withScheme)
                val host = uri.host
                if (uri.scheme != "https" || host.isNullOrBlank()) null
                else if (uri.port != -1) "https://$host:${uri.port}" else "https://$host"
            } catch (e: Exception) {
                null
            }
        }
    }
}
