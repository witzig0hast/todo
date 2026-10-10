package app.todo.client

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Startet die Hintergrundverbindung nach Neustart oder App-Update, wenn das Gerät registriert ist. */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED || intent.action == Intent.ACTION_MY_PACKAGE_REPLACED) {
            if (Prefs(context).deviceToken != null) PushService.start(context)
        }
    }
}
