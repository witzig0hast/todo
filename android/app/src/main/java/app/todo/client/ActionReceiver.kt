package app.todo.client

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationManagerCompat
import androidx.core.app.RemoteInput
import org.json.JSONObject

/** Knöpfe in der Benachrichtigung ("Erledigt", "10 Min. später") -> POST /api/actions mit dem signierten Token. */
class ActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == ACTION_REPLY) return reply(context, intent)
        if (intent.action != ACTION) return
        val token = intent.getStringExtra(EXTRA_TOKEN) ?: return
        val action = intent.getStringExtra(EXTRA_ACTION) ?: return
        val notificationId = intent.getIntExtra(EXTRA_NOTIFICATION_ID, -1)
        val server = Prefs(context).serverUrl ?: return
        val pending = goAsync()
        Thread {
            try {
                val body = JSONObject().put("token", token).put("action", action).put("minutes", 10)
                val ok = Http.postJson("$server/api/actions", body)
                if (ok && notificationId >= 0) NotificationManagerCompat.from(context).cancel(notificationId)
            } finally {
                pending.finish()
            }
        }.start()
    }

    /** Antwort auf eine Agent-Rückfrage: Auswahlknopf (EXTRA_ANSWER) oder Texteingabe (RemoteInput). */
    private fun reply(context: Context, intent: Intent) {
        val token = intent.getStringExtra(EXTRA_TOKEN) ?: return
        val notificationId = intent.getIntExtra(EXTRA_NOTIFICATION_ID, -1)
        val text = intent.getStringExtra(EXTRA_ANSWER)
            ?: RemoteInput.getResultsFromIntent(intent)?.getCharSequence(KEY_REPLY)?.toString()
            ?: return
        if (text.isBlank()) return
        val server = Prefs(context).serverUrl ?: return
        val pending = goAsync()
        Thread {
            try {
                val ok = Http.postJson("$server/api/actions/reply", JSONObject().put("token", token).put("text", text.take(500)))
                if (notificationId >= 0) Notifier.showDone(context, notificationId, if (ok) "Antwort gesendet: ${text.take(60)}" else "Antwort konnte nicht gesendet werden")
            } finally {
                pending.finish()
            }
        }.start()
    }

    companion object {
        const val ACTION = "app.todo.client.NOTIFICATION_ACTION"
        const val ACTION_REPLY = "app.todo.client.NOTIFICATION_REPLY"
        const val EXTRA_ANSWER = "answer"
        const val KEY_REPLY = "reply_text"
        const val EXTRA_TOKEN = "token"
        const val EXTRA_ACTION = "action"
        const val EXTRA_NOTIFICATION_ID = "notification_id"
    }
}
