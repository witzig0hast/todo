package app.todo.client

import android.Manifest
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.location.LocationManager
import android.net.Uri
import android.os.Build
import org.json.JSONObject

/**
 * Standort-Erinnerungen ohne Google-Dienste: Android-Annäherungsalarme (LocationManager.addProximityAlert)
 * für jede offene Aufgabe mit Ort. Die Liste kommt vom Server (`/api/devices/geofences`).
 */
object Geofences {
    private const val ACTION = "app.todo.client.GEOFENCE"
    private const val CODE_BASE = 100_000

    fun allowed(context: Context): Boolean {
        val fine = context.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        val background = Build.VERSION.SDK_INT < 29 ||
            context.checkSelfPermission(Manifest.permission.ACCESS_BACKGROUND_LOCATION) == PackageManager.PERMISSION_GRANTED
        return fine && background
    }

    private fun pendingIntent(context: Context, todoId: Int): PendingIntent {
        val intent = Intent(context, GeofenceReceiver::class.java).apply {
            action = ACTION
            data = Uri.parse("todo://geofence/$todoId")
        }
        // MUTABLE nötig: LocationManager ergänzt KEY_PROXIMITY_ENTERING. Ziel ist explizit der eigene Receiver.
        return PendingIntent.getBroadcast(context, CODE_BASE + todoId, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE)
    }

    /** Läuft im Hintergrund-Thread: Orte vom Server holen und Annäherungsalarme neu setzen. */
    fun sync(context: Context) {
        val prefs = Prefs(context)
        val token = prefs.deviceToken ?: return
        val server = prefs.serverUrl ?: return
        val lm = context.getSystemService(LocationManager::class.java) ?: return
        val text = Http.get("$server/api/devices/geofences", token) ?: return
        val list = try { JSONObject(text).getJSONArray("geofences") } catch (e: Exception) { return }
        // alte Alarme entfernen
        for (id in prefs.geofenceIds) {
            try { lm.removeProximityAlert(pendingIntent(context, id)) } catch (_: Exception) {}
        }
        if (!allowed(context)) { prefs.geofenceIds = emptySet(); return }
        val ids = mutableSetOf<Int>()
        val data = JSONObject()
        for (i in 0 until list.length()) {
            val g = list.getJSONObject(i)
            val id = g.getInt("todo_id")
            try {
                lm.addProximityAlert(g.getDouble("lat"), g.getDouble("lon"), g.getInt("radius").toFloat(), -1, pendingIntent(context, id))
                ids.add(id)
                data.put(id.toString(), g)
            } catch (e: SecurityException) {
                break
            } catch (e: Exception) {
                // ungültiger Eintrag -> überspringen
            }
        }
        prefs.geofenceIds = ids
        prefs.geofenceData = data.toString()
    }

    fun entry(context: Context, todoId: Int): JSONObject? = try {
        JSONObject(Prefs(context).geofenceData).optJSONObject(todoId.toString())
    } catch (e: Exception) {
        null
    }
}

/** Wird beim Betreten eines Orts ausgelöst und zeigt die Aufgabe als Benachrichtigung (mit Erledigt/Später). */
class GeofenceReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (!intent.getBooleanExtra(LocationManager.KEY_PROXIMITY_ENTERING, false)) return
        val todoId = intent.data?.lastPathSegment?.toIntOrNull() ?: return
        val g = Geofences.entry(context, todoId) ?: return
        val name = g.optString("name").ifBlank { "einem gespeicherten Ort" }
        Notifier.show(
            context, 200_000 + todoId, "In der Nähe von $name", g.optString("title", "Aufgabe"), "/#/today",
            actionToken = g.optString("token").ifBlank { null },
        )
    }
}
