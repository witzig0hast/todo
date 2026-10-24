package app.todo.client

import android.Manifest
import android.annotation.SuppressLint
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.SystemClock
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.webkit.GeolocationPermissions
import android.webkit.CookieManager
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature

class MainActivity : AppCompatActivity() {
    private lateinit var prefs: Prefs
    private var webView: WebView? = null
    private var pendingMicRequest: PermissionRequest? = null
    private var pendingGeo: Pair<String, GeolocationPermissions.Callback>? = null
    private var unlocked = false
    private var authenticating = false
    private var lastHidden = 0L

    private val notificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    private val microphonePermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            val request = pendingMicRequest
            pendingMicRequest = null
            if (request != null) {
                if (granted) request.grant(arrayOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE)) else request.deny()
            }
        }

    private val locationPermission =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
            val fine = result[Manifest.permission.ACCESS_FINE_LOCATION] == true ||
                checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
            pendingGeo?.let { (origin, cb) -> cb.invoke(origin, fine, false) }
            pendingGeo = null
            if (fine && wantsBackgroundLocation) askBackgroundLocation()
        }

    private val backgroundLocationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            wantsBackgroundLocation = false
            if (granted) Thread { Geofences.sync(applicationContext) }.start()
        }

    private var wantsBackgroundLocation = false

    /** Von der Web-Oberfläche angestoßen: Standort (inkl. Hintergrund) für Erinnerungen an Orten erlauben. */
    fun requestLocationForReminders() {
        wantsBackgroundLocation = true
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
            askBackgroundLocation()
        } else {
            locationPermission.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
        }
    }

    private fun askBackgroundLocation() {
        if (Build.VERSION.SDK_INT < 29 ||
            checkSelfPermission(Manifest.permission.ACCESS_BACKGROUND_LOCATION) == PackageManager.PERMISSION_GRANTED
        ) {
            wantsBackgroundLocation = false
            Thread { Geofences.sync(applicationContext) }.start()
            return
        }
        AlertDialog.Builder(this)
            .setTitle("Standort im Hintergrund")
            .setMessage("Damit Todo dich an einem Ort erinnern kann, während die App geschlossen ist, wähle im nächsten Schritt „Immer zulassen“.")
            .setPositiveButton("Weiter") { _, _ -> backgroundLocationPermission.launch(Manifest.permission.ACCESS_BACKGROUND_LOCATION) }
            .setNegativeButton("Abbrechen") { _, _ -> wantsBackgroundLocation = false }
            .show()
    }

    /** Von der Web-Oberfläche angestoßen: App-Sperre ein/aus. */
    fun setAppLock(enabled: Boolean) {
        prefs.appLock = enabled
        unlocked = true
        applySecureFlag()
    }

    private fun applySecureFlag() {
        // Mit App-Sperre: Inhalt nicht in der App-Übersicht und nicht in Screenshots zeigen
        if (prefs.appLock) window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)
        else window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
    }

    private fun requireUnlock() {
        if (!prefs.appLock || authenticating) return
        if (unlocked && SystemClock.elapsedRealtime() - lastHidden < LOCK_GRACE_MS) return
        unlocked = false
        val authenticators = if (Build.VERSION.SDK_INT >= 30) {
            BiometricManager.Authenticators.BIOMETRIC_WEAK or BiometricManager.Authenticators.DEVICE_CREDENTIAL
        } else {
            BiometricManager.Authenticators.BIOMETRIC_WEAK
        }
        if (BiometricManager.from(this).canAuthenticate(authenticators) != BiometricManager.BIOMETRIC_SUCCESS) {
            // keine Bildschirmsperre/Biometrie eingerichtet -> Sperre wäre wirkungslos
            unlocked = true
            Toast.makeText(this, "App-Sperre: Bitte zuerst eine Bildschirmsperre einrichten.", Toast.LENGTH_LONG).show()
            return
        }
        webView?.visibility = View.INVISIBLE
        authenticating = true
        val info = BiometricPrompt.PromptInfo.Builder()
            .setTitle("Todo entsperren")
            .setAllowedAuthenticators(authenticators)
            .apply { if (Build.VERSION.SDK_INT < 30) setNegativeButtonText("Abbrechen") }
            .build()
        BiometricPrompt(this, ContextCompat.getMainExecutor(this), object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                authenticating = false
                unlocked = true
                webView?.visibility = View.VISIBLE
            }

            override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                authenticating = false
                finish() // abgebrochen -> App schließen, Inhalt bleibt verborgen
            }
        }).authenticate(info)
    }

    override fun onStop() {
        super.onStop()
        if (!authenticating) lastHidden = SystemClock.elapsedRealtime()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = Prefs(this)
        Notifier.ensureChannels(this)
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                val w = webView
                if (w != null && w.canGoBack()) {
                    w.goBack()
                } else {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            }
        })
        applySecureFlag()
        if (prefs.serverUrl == null) showSetup() else showWeb(intent)
        if (intent?.getBooleanExtra(EXTRA_UPDATE, false) == true) Updater.install(this)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        if (intent.getBooleanExtra(EXTRA_UPDATE, false)) {
            Updater.install(this)
            return
        }
        val server = prefs.serverUrl ?: return
        val target = targetPath(intent) ?: return
        val w = webView
        if (w == null) showWeb(intent) else w.loadUrl(server + target)
    }

    /** Ziel aus Benachrichtigung (EXTRA_URL) oder aus "Teilen" (ACTION_SEND, Text). */
    private fun targetPath(intent: Intent?): String? {
        if (intent == null) return null
        if (intent.action == Intent.ACTION_SEND && intent.type?.startsWith("text/") == true) {
            val text = listOfNotNull(intent.getStringExtra(Intent.EXTRA_SUBJECT), intent.getStringExtra(Intent.EXTRA_TEXT))
                .joinToString("\n").trim().take(2000)
            return if (text.isEmpty()) null else "/#/share?text=" + Uri.encode(text)
        }
        val path = intent.getStringExtra(EXTRA_URL)
        return if (isSafePath(path)) path else null
    }

    override fun onResume() {
        super.onResume()
        requireUnlock()
        // Falls das System den Dienst beendet hat: bei registriertem Gerät wieder starten
        if (prefs.deviceToken != null) {
            PushService.start(this)
            Updater.checkAsync(this)
            TodoWidget.refresh(this)
        }
    }

    override fun onPause() {
        CookieManager.getInstance().flush()
        super.onPause()
    }

    override fun onDestroy() {
        webView?.destroy()
        webView = null
        super.onDestroy()
    }

    // ------------------------------------------------------------------ Ersteinrichtung
    private fun dp(value: Int): Int =
        TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value.toFloat(), resources.displayMetrics).toInt()

    private fun showSetup() {
        webView?.destroy()
        webView = null
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(28), dp(28), dp(28), dp(28))
            setBackgroundColor(Color.parseColor("#09090B"))
        }
        val title = TextView(this).apply {
            text = getString(R.string.setup_title)
            setTextColor(Color.parseColor("#FAFAFA"))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 24f)
        }
        val infoText = TextView(this).apply {
            text = getString(R.string.setup_hint)
            setTextColor(Color.parseColor("#A1A1AA"))
            setPadding(0, dp(8), 0, dp(20))
        }
        val input = EditText(this).apply {
            setSingleLine()
            inputType = android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_URI
            setTextColor(Color.parseColor("#FAFAFA"))
            setHintTextColor(Color.parseColor("#71717A"))
            this.hint = "https://todo.example.com"
            setText(prefs.serverUrl ?: "")
        }
        val connect = Button(this).apply {
            text = getString(R.string.setup_connect)
            setOnClickListener {
                val url = Prefs.normalizeServerUrl(input.text.toString())
                if (url == null) {
                    Toast.makeText(this@MainActivity, R.string.setup_invalid, Toast.LENGTH_LONG).show()
                } else {
                    prefs.serverUrl = url
                    showWeb(null)
                }
            }
        }
        root.addView(title)
        root.addView(infoText)
        root.addView(input, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        root.addView(connect, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { topMargin = dp(16) })
        setContentView(root)
    }

    // ------------------------------------------------------------------ Web-Oberfläche
    private fun serverHost(): String? = prefs.serverUrl?.let { Uri.parse(it).host }

    private fun isSafePath(path: String?): Boolean =
        path != null && path.startsWith("/") && !path.startsWith("//") && !path.contains("\\") && !path.contains(" ")

    private fun sameOrigin(uri: Uri): Boolean {
        val server = prefs.serverUrl?.let { Uri.parse(it) } ?: return false
        return uri.scheme == server.scheme && uri.host == server.host && uri.port == server.port
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun showWeb(launchIntent: Intent?) {
        val server = prefs.serverUrl ?: return showSetup()
        val web = WebView(this)
        webView = web
        web.setBackgroundColor(Color.parseColor("#09090B"))
        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            mediaPlaybackRequiresUserGesture = false
            allowFileAccess = false
            allowContentAccess = false
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            setSupportZoom(false)
            userAgentString = userAgentString + " TodoAndroid/" + BuildConfig.VERSION_NAME
        }
        CookieManager.getInstance().apply {
            setAcceptCookie(true)
            setAcceptThirdPartyCookies(web, false)
        }

        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val uri = request.url
                when (uri.scheme) {
                    "todoapp" -> { // Link der Fehlerseite: Server ändern
                        if (uri.host == "reset") showSetup()
                        return true
                    }
                    "mailto", "tel" -> { openExternal(uri); return true }
                    "https" -> Unit
                    else -> return true // alles andere (http, intent:, file: ...) blockieren
                }
                val host = uri.host ?: return true
                if (host == serverHost() || host in prefs.extraHosts) return false
                // Weiterleitung von einem erlaubten Host (z. B. zum SSO-Anbieter): im WebView lassen und merken
                if (request.isRedirect && request.isForMainFrame) {
                    prefs.extraHosts = prefs.extraHosts + host
                    return false
                }
                openExternal(uri)
                return true
            }

            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                if (request.isForMainFrame) showOfflinePage(view)
            }
        }

        web.settings.setGeolocationEnabled(true)
        web.webChromeClient = object : WebChromeClient() {
            override fun onGeolocationPermissionsShowPrompt(origin: String, callback: GeolocationPermissions.Callback) {
                if (!sameOrigin(Uri.parse(origin))) {
                    callback.invoke(origin, false, false)
                    return
                }
                if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
                    callback.invoke(origin, true, false)
                } else {
                    pendingGeo = origin to callback
                    locationPermission.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
                }
            }

            override fun onPermissionRequest(request: PermissionRequest) {
                val micOnly = request.resources.all { it == PermissionRequest.RESOURCE_AUDIO_CAPTURE }
                if (!sameOrigin(request.origin) || !micOnly) {
                    request.deny()
                    return
                }
                if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                    request.grant(arrayOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE))
                } else {
                    pendingMicRequest?.deny()
                    pendingMicRequest = request
                    microphonePermission.launch(Manifest.permission.RECORD_AUDIO)
                }
            }
        }

        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
            WebViewCompat.addWebMessageListener(web, "TodoAndroid", setOf(server), Bridge(this, prefs))
        }

        setContentView(web)
        web.loadUrl(server + (targetPath(launchIntent) ?: "/"))
    }

    private fun showOfflinePage(view: WebView) {
        val server = prefs.serverUrl ?: return
        val html = """
            <html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
            <body style="margin:0;background:#09090b;color:#fafafa;font-family:sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center;text-align:center">
            <div style="padding:24px"><h2>Server nicht erreichbar</h2>
            <p style="color:#a1a1aa">${server.replace("<", "")}</p>
            <p><a href="$server/" style="display:inline-block;padding:12px 20px;border-radius:8px;background:#fafafa;color:#09090b;text-decoration:none;font-weight:600">Erneut versuchen</a></p>
            <p><a href="todoapp://reset" style="color:#a1a1aa">Server ändern</a></p></div></body></html>
        """.trimIndent()
        view.loadDataWithBaseURL(server, html, "text/html", "utf-8", null)
    }

    private fun openExternal(uri: Uri) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, uri))
        } catch (_: Exception) {
        }
    }

    companion object {
        const val EXTRA_URL = "url"
        const val EXTRA_UPDATE = "update"
        private const val LOCK_GRACE_MS = 30_000L
    }
}
