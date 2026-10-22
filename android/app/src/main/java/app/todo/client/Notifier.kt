package app.todo.client

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat

object Notifier {
    const val CHANNEL_MESSAGES = "messages"
    const val CHANNEL_SERVICE = "service"

    fun ensureChannels(context: Context) {
        if (Build.VERSION.SDK_INT < 26) return
        val nm = context.getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_MESSAGES, context.getString(R.string.channel_messages), NotificationManager.IMPORTANCE_HIGH)
                .apply { description = context.getString(R.string.channel_messages_desc) }
        )
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_SERVICE, context.getString(R.string.channel_service), NotificationManager.IMPORTANCE_MIN)
                .apply { description = context.getString(R.string.channel_service_desc) }
        )
    }

    fun allowed(context: Context): Boolean {
        if (Build.VERSION.SDK_INT >= 33 &&
            context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) return false
        return NotificationManagerCompat.from(context).areNotificationsEnabled()
    }

    fun openAppIntent(context: Context, requestCode: Int, url: String?): PendingIntent {
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
            if (!url.isNullOrBlank()) putExtra(MainActivity.EXTRA_URL, url)
        }
        return PendingIntent.getActivity(context, requestCode, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }

    private fun actionIntent(context: Context, notificationId: Int, token: String, action: String, code: Int): PendingIntent {
        val intent = Intent(context, ActionReceiver::class.java).apply {
            this.action = ActionReceiver.ACTION
            putExtra(ActionReceiver.EXTRA_TOKEN, token)
            putExtra(ActionReceiver.EXTRA_ACTION, action)
            putExtra(ActionReceiver.EXTRA_NOTIFICATION_ID, notificationId)
        }
        return PendingIntent.getBroadcast(context, code, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }

    /**
     * Zeigt eine Nachricht als Benachrichtigung. Mit Aktions-Token (Erinnerungen, Orte) gibt es die Knöpfe
     * "Erledigt" und "10 Min. später". Gibt false zurück, wenn Benachrichtigungen nicht erlaubt sind.
     */
    @Suppress("MissingPermission")
    fun show(
        context: Context, id: Int, title: String, body: String, url: String?,
        actionToken: String? = null,
    ): Boolean {
        if (!allowed(context)) return false
        val builder = NotificationCompat.Builder(context, CHANNEL_MESSAGES)
            .setSmallIcon(R.drawable.ic_stat_check)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setContentIntent(openAppIntent(context, id, url))
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_MESSAGE)
        if (!actionToken.isNullOrBlank()) {
            builder.addAction(0, "Erledigt", actionIntent(context, id, actionToken, "done", id * 4 + 1))
            builder.addAction(0, "10 Min. später", actionIntent(context, id, actionToken, "snooze", id * 4 + 2))
        }
        NotificationManagerCompat.from(context).notify(id, builder.build())
        return true
    }
}
