package app.todo.client

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.view.View
import android.widget.RemoteViews
import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/**
 * Homescreen-Widget: heute fällige und überfällige Aufgaben abhaken, neue anlegen.
 * Daten über den Geräte-Token (GET /api/app/widget), zwischengespeichert für den Offline-Fall.
 * Mit aktiver App-Sperre zeigt das Widget nur Zahlen, keine Titel.
 */
class TodoWidget : AppWidgetProvider() {

    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        render(context)
        load(context, goAsync())
    }

    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)
        when (intent.action) {
            ACTION_REFRESH -> load(context, goAsync())
            ACTION_DONE -> {
                val id = intent.getIntExtra(EXTRA_ID, -1)
                if (id > 0) {
                    removeFromCache(context, id) // sofort ausblenden, dann im Hintergrund melden
                    render(context)
                    load(context, goAsync(), id)
                }
            }
        }
    }

    companion object {
        const val ACTION_REFRESH = "app.todo.client.WIDGET_REFRESH"
        const val ACTION_DONE = "app.todo.client.WIDGET_DONE"
        const val EXTRA_ID = "todo_id"
        private val ROWS = intArrayOf(R.id.w_row0, R.id.w_row1, R.id.w_row2, R.id.w_row3, R.id.w_row4)
        private val CHECKS = intArrayOf(R.id.w_check0, R.id.w_check1, R.id.w_check2, R.id.w_check3, R.id.w_check4)
        private val TITLES = intArrayOf(R.id.w_title0, R.id.w_title1, R.id.w_title2, R.id.w_title3, R.id.w_title4)
        private val DUES = intArrayOf(R.id.w_due0, R.id.w_due1, R.id.w_due2, R.id.w_due3, R.id.w_due4)

        /** Von außen (App, Push-Dienst): Widget neu laden, falls eines auf dem Homescreen liegt. */
        fun refresh(context: Context) {
            if (ids(context).isEmpty()) return
            context.sendBroadcast(Intent(context, TodoWidget::class.java).setAction(ACTION_REFRESH))
        }

        private fun ids(context: Context): IntArray =
            AppWidgetManager.getInstance(context).getAppWidgetIds(ComponentName(context, TodoWidget::class.java))

        private fun load(context: Context, pending: PendingResult?, doneId: Int = -1) {
            val app = context.applicationContext
            Thread {
                try {
                    val prefs = Prefs(app)
                    val server = prefs.serverUrl
                    val token = prefs.deviceToken
                    if (server != null && token != null) {
                        if (doneId > 0) Http.postJson("$server/api/app/todos/$doneId/done", JSONObject(), token)
                        Http.get("$server/api/app/widget", token)?.let { prefs.widgetData = it }
                    }
                    render(app)
                } catch (_: Exception) {
                } finally {
                    pending?.finish()
                }
            }.start()
        }

        private fun removeFromCache(context: Context, id: Int) {
            val prefs = Prefs(context)
            val data = try { JSONObject(prefs.widgetData) } catch (_: Exception) { return }
            val items = data.optJSONArray("items") ?: return
            val rest = JSONArray()
            for (i in 0 until items.length()) items.optJSONObject(i)?.let { if (it.optInt("id") != id) rest.put(it) }
            data.put("items", rest)
            prefs.widgetData = data.toString()
        }

        private fun openApp(context: Context, path: String, code: Int): PendingIntent =
            Notifier.openAppIntent(context, code, path)

        private fun broadcast(context: Context, action: String, code: Int, id: Int = -1): PendingIntent {
            val intent = Intent(context, TodoWidget::class.java).setAction(action).putExtra(EXTRA_ID, id)
            return PendingIntent.getBroadcast(context, code, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        }

        private fun formatDue(iso: String?): String {
            if (iso.isNullOrBlank() || iso == "null") return ""
            return try {
                val dt = Instant.parse(iso).atZone(ZoneId.systemDefault())
                val days = java.time.temporal.ChronoUnit.DAYS.between(LocalDate.now(), dt.toLocalDate())
                val time = dt.format(DateTimeFormatter.ofPattern("HH:mm"))
                when {
                    days == 0L -> time
                    days == 1L -> "Morgen $time"
                    days == -1L -> "Gestern"
                    else -> dt.format(DateTimeFormatter.ofPattern("EE dd.MM.", Locale.GERMAN))
                }
            } catch (_: Exception) {
                ""
            }
        }

        fun render(context: Context) {
            val widgetIds = ids(context)
            if (widgetIds.isEmpty()) return
            val prefs = Prefs(context)
            val views = RemoteViews(context.packageName, R.layout.widget_todo)
            val data = try { JSONObject(prefs.widgetData) } catch (_: Exception) { JSONObject() }
            val items = data.optJSONArray("items") ?: JSONArray()
            val registered = prefs.deviceToken != null
            val hidden = prefs.appLock
            val today = data.optInt("today", 0)
            val overdue = data.optInt("overdue", 0)
            views.setTextViewText(R.id.w_subtitle, when {
                !registered -> "In der App anmelden"
                today == 0 && items.length() == 0 -> "Nichts offen"
                overdue > 0 -> "$today heute · $overdue überfällig"
                else -> "$today heute · ${data.optInt("open", 0)} offen"
            })
            for (i in ROWS.indices) {
                val item = if (!hidden && i < items.length()) items.optJSONObject(i) else null
                if (item == null) {
                    views.setViewVisibility(ROWS[i], View.GONE)
                    continue
                }
                val id = item.optInt("id")
                views.setViewVisibility(ROWS[i], View.VISIBLE)
                views.setTextViewText(TITLES[i], item.optString("title"))
                views.setTextViewText(DUES[i], formatDue(item.optString("due_at")))
                views.setTextColor(DUES[i], if (item.optBoolean("overdue")) Color.parseColor("#F87171") else Color.parseColor("#A1A1AA"))
                views.setOnClickPendingIntent(CHECKS[i], broadcast(context, ACTION_DONE, 1000 + id, id))
                views.setOnClickPendingIntent(TITLES[i], openApp(context, "/#/all", 2000 + i))
            }
            val empty = registered && !hidden && items.length() == 0
            views.setViewVisibility(R.id.w_empty, if (empty || hidden) View.VISIBLE else View.GONE)
            views.setTextViewText(R.id.w_empty, if (hidden) "App-Sperre aktiv – Titel ausgeblendet" else "Alles erledigt.")
            views.setOnClickPendingIntent(R.id.w_header, openApp(context, "/#/today", 2100))
            views.setOnClickPendingIntent(R.id.w_refresh, broadcast(context, ACTION_REFRESH, 2101))
            val add = Intent(context, QuickAddActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
            views.setOnClickPendingIntent(R.id.w_add, PendingIntent.getActivity(context, 2102, add,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE))
            AppWidgetManager.getInstance(context).updateAppWidget(widgetIds, views)
        }
    }
}
