package app.todo.client

import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.speech.RecognizerIntent
import android.util.TypedValue
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.EditText
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONObject

/**
 * Kleines Eingabefenster „Neue Aufgabe“ – vom Widget, App-Shortcut und der Schnelleinstellungs-Kachel.
 * Der Text wird wie in der App ausgewertet („morgen 15 Uhr Zahnarzt #privat !!“).
 */
class QuickAddActivity : AppCompatActivity() {
    private lateinit var input: EditText
    private lateinit var save: Button

    private val speech = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val text = result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull() ?: return@registerForActivityResult
        input.setText(text)
        input.setSelection(text.length)
    }

    private fun dp(v: Int) = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v.toFloat(), resources.displayMetrics).toInt()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = Prefs(this)
        val server = prefs.serverUrl
        val token = prefs.deviceToken
        if (server == null || token == null) {
            Toast.makeText(this, "Bitte zuerst die Todo-App öffnen und anmelden.", Toast.LENGTH_LONG).show()
            startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            finish()
            return
        }
        setTitle("Neue Aufgabe")
        input = EditText(this).apply {
            hint = "z. B. morgen 15 Uhr Zahnarzt #privat !!"
            setTextColor(Color.parseColor("#FAFAFA"))
            setHintTextColor(Color.parseColor("#71717A"))
            setSingleLine()
            imeOptions = EditorInfo.IME_ACTION_DONE
            setOnEditorActionListener { _, action, _ -> if (action == EditorInfo.IME_ACTION_DONE) { submit(server, token); true } else false }
            intent.getStringExtra(Intent.EXTRA_TEXT)?.let { setText(it.take(300)) }
        }
        val voiceIntent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE, "de-DE")
            .putExtra(RecognizerIntent.EXTRA_PROMPT, "Aufgabe sprechen")
        val canSpeak = voiceIntent.resolveActivity(packageManager) != null
        val mic = ImageButton(this).apply {
            setImageResource(R.drawable.ic_mic)
            setBackgroundColor(Color.TRANSPARENT)
            contentDescription = "Spracheingabe"
            setOnClickListener { try { speech.launch(voiceIntent) } catch (_: Exception) { } }
        }
        save = Button(this).apply { text = "Speichern"; setOnClickListener { submit(server, token) } }
        val hint = TextView(this).apply {
            text = "Datum, Uhrzeit, #tags, @liste und !! werden erkannt."
            setTextColor(Color.parseColor("#A1A1AA"))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 12f)
            setPadding(0, dp(6), 0, dp(10))
        }
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            if (canSpeak) addView(mic, LinearLayout.LayoutParams(dp(48), dp(48)))
            addView(android.view.View(context), LinearLayout.LayoutParams(0, 1, 1f))
            addView(save)
        }
        setContentView(LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(12), dp(20), dp(16))
            addView(input)
            addView(hint)
            addView(row)
        })
        input.requestFocus()
        if (intent.getBooleanExtra(EXTRA_VOICE, false) && canSpeak && savedInstanceState == null) speech.launch(voiceIntent)
    }

    private fun submit(server: String, token: String) {
        val text = input.text.toString().trim()
        if (text.isEmpty()) return
        save.isEnabled = false
        Thread {
            val (code, body) = Http.postJsonResult("$server/api/app/quick", JSONObject().put("text", text), token)
            runOnUiThread {
                if (code == 201) {
                    val title = try { JSONObject(body ?: "{}").optString("title", text) } catch (_: Exception) { text }
                    Toast.makeText(this, "Gespeichert: $title", Toast.LENGTH_SHORT).show()
                    TodoWidget.refresh(this)
                    finish()
                } else {
                    save.isEnabled = true
                    Toast.makeText(this, if (code == 0) "Keine Verbindung zum Server." else "Fehler ($code) – bitte in der App erneut anmelden.", Toast.LENGTH_LONG).show()
                }
            }
        }.start()
    }

    companion object {
        const val EXTRA_VOICE = "voice"
    }
}
