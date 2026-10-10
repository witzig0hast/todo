package app.todo.client

import android.Manifest
import android.annotation.SuppressLint
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.util.TypedValue
import android.view.Gravity
import android.view.ViewGroup
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
import androidx.appcompat.app.AppCompatActivity
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature

class MainActivity : AppCompatActivity() {
    private lateinit var prefs: Prefs
    private var webView: WebView? = null
    private var pendingMicRequest: PermissionRequest? = null

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
        if (prefs.serverUrl == null) showSetup() else showWeb(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        val server = prefs.serverUrl ?: return
        val path = intent.getStringExtra(EXTRA_URL)
        if (isSafePath(path)) webView?.loadUrl(server + path)
    }

    override fun onResume() {
        super.onResume()
        // Falls das System den Dienst beendet hat: bei registriertem Gerät wieder starten
        if (prefs.deviceToken != null) PushService.start(this)
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
        val hint = TextView(this).apply {
            text = getString(R.string.setup_hint)
            setTextColor(Color.parseColor("#A1A1AA"))
            setPadding(0, dp(8), 0, dp(20))
        }
        val input = EditText(this).apply {
            setSingleLine()
            inputType = android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_URI
            setTextColor(Color.parseColor("#FAFAFA"))
            setHintTextColor(Color.parseColor("#71717A"))
            hint = "https://todo.example.com"
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
        root.addView(hint)
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

        web.webChromeClient = object : WebChromeClient() {
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
        val path = launchIntent?.getStringExtra(EXTRA_URL)
        web.loadUrl(if (isSafePath(path)) server + path else "$server/")
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
    }
}
