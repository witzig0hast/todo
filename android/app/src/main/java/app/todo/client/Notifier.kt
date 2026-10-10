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

    /** Zeigt eine Nachricht als Benachrichtigung. Gibt false zurück, wenn Benachrichtigungen nicht erlaubt sind. */
    @Suppress("MissingPermission")
    fun show(context: Context, id: Int, title: String, body: String, url: String?): Boolean {
        if (!allowed(context)) return false
        val notification = NotificationCompat.Builder(context, CHANNEL_MESSAGES)
            .setSmallIcon(R.drawable.ic_stat_check)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setContentIntent(openAppIntent(context, id, url))
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_MESSAGE)
            .build()
        NotificationManagerCompat.from(context).notify(id, notification)
        return true
    }
}
