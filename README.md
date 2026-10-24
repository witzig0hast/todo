# Todo

Selbst gehostete, sichere To-do-App als einzelner Docker-Container – mit **Ollama-KI**, **Whisper-Spracheingabe**
(Wyoming), **Agent Bus**, Web-Push und einer PWA-Oberfläche für Handy, Tablet und PC.

## Funktionen

- **Benutzer:** Der erste Benutzer wird automatisch **Admin**. Jede weitere Registrierung bleibt `pending`, bis ein
  Admin sie freigibt (Admin-Bereich: freigeben, ablehnen, sperren, Rolle ändern, löschen, Protokoll).
- **Single Sign-On (OpenID Connect):** Anmeldung über **Authentik** oder jeden anderen OIDC-Anbieter (Keycloak, Authelia,
  Google, Microsoft, ...), auch mehrere gleichzeitig. Siehe Abschnitt „Single Sign-On“.
- **Aufgaben:** Listen, Prioritäten, Fälligkeit, Notizen, Unteraufgaben, **Tags** (`#tag` im Titel), **Wiederholung**
  (täglich/wöchentlich/monatlich/jährlich, Wochentage, „nach Erledigung“ – in deiner Zeitzone, sommerzeitfest),
  **mehrere Erinnerungen** pro Aufgabe, **Schlummern** (10 Min. bis morgen früh), **Suche**, **gespeicherte Filter**,
  **Kalenderansicht**, **Anhänge** (Bilder, PDF, Text, bis 10 MB), **Standort-Erinnerungen** (Android-App),
  Wisch-Gesten (rechts = erledigt, links = löschen), Tastaturkürzel (`n` oder `/` = neue Aufgabe, `Esc` = Details schließen).
- **Schnelleingabe ohne KI:** „morgen 15 Uhr Zahnarzt #privat !!“, „jeden Montag Müll @haushalt“, „in 30 min Pizza“ – Datum,
  Uhrzeit, Priorität (`!`, `!!`, `!!!`, `!hoch`), Liste (`@name`), Tags und Wiederholung werden sofort erkannt und vor dem
  Speichern als Vorschau angezeigt („Nur Text“ schaltet die Erkennung ab).
- **Papierkorb & Rückgängig:** Gelöschtes (auch mehrere auf einmal oder „Aufräumen“) lässt sich direkt per „Rückgängig“ oder
  30 Tage lang im Papierkorb wiederherstellen – inkl. Unteraufgaben, Anhängen und erfasster Zeit.
- **Mehrfachauswahl:** Auswahl-Knopf oder lange auf eine Aufgabe drücken → erledigen, verschieben, taggen, Datum/Priorität setzen, löschen.
- **Vorlagen:** Checklisten wie „Urlaub packen“ mit Unteraufgaben und relativer Fälligkeit („nach 2 Tagen um 18:00“); jede
  Aufgabe lässt sich in den Details „Als Vorlage“ speichern.
- **Fokus-Timer & Statistik:** 15/25/50-Minuten-Timer an einer Aufgabe (Zeit wird erfasst), Statistik mit erledigt pro Woche
  und Wochentag, Serie, Fokuszeit, Dauerbrennern – optional als **Wochenrückblick** sonntags um 18 Uhr.
- **Geteilte Listen:** Listen per Benutzername mit anderen freigegebenen Benutzern teilen; Änderungen erscheinen live bei allen.
- **Board & Projekte:** jede Liste auch als Board (Offen · In Arbeit · Erledigt, Ziehen mit der Maus, am Handy über „…“);
  Listen können **Projekte** sein – mit Fortschrittsbalken und Termin.
- **Abhängigkeiten:** „wartet auf …“ zwischen Aufgaben (Kreise werden verhindert); wird die letzte Voraussetzung erledigt,
  kommt eine Benachrichtigung „Kann losgehen“.
- **Zuweisen, Kommentare, Verlauf:** in geteilten Listen Aufgaben an Mitglieder zuweisen (Ansicht „Mir zugewiesen“),
  Kommentare mit **@Erwähnungen** (Push an die Erwähnten) und ein Änderungsverlauf pro Aufgabe (wer hat wann was geändert).
- **Einladungslinks:** Admins erzeugen Links mit Ablaufdatum und Nutzungszahl – wer sich darüber registriert, ist sofort freigegeben.
- **Kalender-Abo (ICS):** geheimer Link für Handy-, Thunderbird-, Outlook- oder Nextcloud-Kalender (jederzeit neu erzeugbar/widerrufbar).
- **Ollama:** Freitext → Aufgabe(n) („morgen 15 Uhr Zahnarzt anrufen und Milch kaufen“ ergibt zwei Aufgaben),
  Unteraufgaben vorschlagen, Tagesplan, Chat-Assistent. Der Assistent kann **Aktionen vorschlagen** (anlegen, erledigen,
  verschieben, ...), ausgeführt wird erst nach deiner Bestätigung. **Morgen-Zusammenfassung** als Benachrichtigung zur
  gewünschten Uhrzeit. Das Modell ist pro Benutzer wählbar.
- **Mehr KI:** **Foto → Aufgaben** (Zettel, Brief, Rechnung fotografieren; ein Vision-Modell wie `qwen2.5vl:7b` erkennt Fristen
  und Beträge, das Foto wird auf Wunsch angehängt), **Woche planen** (verteilt offene Aufgaben auf die nächsten 7 Tage – als
  Vorschlag), **Suche nach Bedeutung** („Auto“ findet „TÜV-Termin“, über Embeddings, Standard `bge-m3`), **Duplikat-Hinweis**
  beim Anlegen plus Duplikat-Übersicht im Assistenten, **Tags & Liste vorschlagen** in den Details. Modelle in den Einstellungen
  wählbar; einmalig laden: `ollama pull qwen2.5vl:7b` und `ollama pull bge-m3`.
- **Whisper:** Mikrofon-Button → Aufnahme wird im Browser in 16-kHz-WAV umgewandelt, das Backend spricht per
  Wyoming-Protokoll mit deinem `wyoming-whisper` (Port 10300) → Text → KI-Vorschlag. Funktioniert auch für **Sprachbefehle**
  („erledige Zahnarzt“) und Diktat mehrerer Aufgaben. Audio wird nie gespeichert.
- **Mail → Aufgabe:** pro Benutzer ein IMAP-Postfach (TLS/STARTTLS), Betreff = Titel, Text = Notizen; nur Mails von erlaubten
  Absendern werden übernommen. Das Passwort liegt verschlüsselt in `/data`. Am besten ein eigenes Postfach dafür anlegen.
- **Agent Bus** (Konzept aus [ownai](https://github.com/witzig0hast/ownai)): pro Benutzer eigene Agents mit eigenem
  API-Key (`X-Agent-Key`, nur als SHA-256-Hash gespeichert, rotierbar), Rechte pro Agent (`send`, `todos:read`,
  `todos:write`, `notify`), Text-Nachrichten und Tasks mit Status, Posteingang per Polling **oder Live-Stream (SSE)**,
  vollständiges Log mit **Zustellstatus** im UI. Eingebaute Task-Typen: `todo.create`, `todo.list`, `todo.complete`,
  `device.notify`. Dazu **Webhooks** (eingehende URL pro Agent, z. B. für GitHub, Uptime Kuma, Home Assistant),
  **Regeln** („wenn Agent X `failed` meldet → Aufgabe anlegen / Gerät benachrichtigen“) und **Rückfragen**, die du direkt aus
  der Benachrichtigung beantwortest (Task-Typ `ask`, bis zu 3 Antwort-Knöpfe oder Freitext).
- **Integrationen:** persönliche **API-Tokens** (lesen/schreiben, widerrufbar) für **Home Assistant** (Sensoren „offen/heute/
  überfällig“, Aufgaben per Assist-Sprachbefehl – YAML-Vorlage in den Einstellungen), Skripte (`/api/v1/...`) und
  **KI-Agenten per MCP** (`/api/mcp`, z. B. `claude mcp add --transport http todo https://todo.example.com/api/mcp --header
  "Authorization: Bearer tdk_…"`).
- **Weitere Benachrichtigungskanäle:** ntfy, Gotify, Telegram, Matrix und E-Mail (SMTP) – je Kanal „alle“ oder „nur dringende“.
  Server im internen Netz (z. B. Gotify im Heimnetz) dürfen standardmäßig nur Admins eintragen (`NOTIFY_PRIVATE_HOSTS`).
- **Import:** Todoist (CSV), Google Tasks (Takeout `Tasks.json`), Microsoft To Do/Outlook bzw. jede Tabelle (CSV) und der
  eigene JSON-Export – mit „Rückgängig“.
- **Push:** Fälligkeits-Erinnerungen mit Knöpfen **Erledigt/Später**, Agent-Nachrichten, neue Registrierungen (an Admins) –
  Web-Push mit VAPID (Schlüssel werden beim ersten Start in `/data` erzeugt).
- **Android-App** (`android/`): Nachrichten an einzelne Geräte, Aktionen und Antworten direkt in der Benachrichtigung,
  **Ruhezeiten pro Gerät** (dringende Nachrichten kommen trotzdem), **App-Sperre per Fingerabdruck**, Standort-Erinnerungen,
  „Teilen mit Todo“ aus anderen Apps, **Homescreen-Widget**, **App-Shortcuts**, **Schnelleinstellungs-Kachel** und
  **Updates über den eigenen Server**. Details: [`android/README.md`](android/README.md).
- **Sicherheit fürs Konto:** **Zwei-Faktor-Anmeldung (TOTP)** mit QR-Code und 10 Wiederherstellungscodes, **Passkeys**
  (Fingerabdruck/Face ID/Sicherheitsschlüssel, Anmeldung ohne Passwort), Liste aller **angemeldeten Geräte** mit Abmelden
  einzeln oder „alle anderen“.
- **Backup & Export:** tägliches SQLite-Backup nach `/data/backups` (die letzten `BACKUP_KEEP`, Standard 14), manuell im
  Admin-Bereich auslösbar und herunterladbar; jeder Benutzer kann seine Daten als JSON oder CSV exportieren.
- **PWA:** installierbar, App-Shell offline, Manifest + Icons (inkl. maskable), Teilen-Ziel. Hell/Dunkel automatisch.

- **Betrieb:** Admin-**Statusseite** (Ollama inkl. fehlender Modelle, Whisper, Push, Android-Geräte, Mail-Abruf, Kanäle,
  Hintergrundjobs, Datenbank, Speicherplatz, Konfiguration) und **Warnung bei Anmeldung von einem neuen Gerät** (Push, App
  und alle Kanäle; bekannte Geräte in den Einstellungen einsehbar und vergessbar).

## Sicherheit

argon2-Passwort-Hashes · Sitzungen als `HttpOnly`/`Secure`/`SameSite=Strict`-Cookie (nur Hash in der DB) ·
CSRF-Token + Origin-Prüfung · Rate-Limits (Login pro Konto/IP mit Sperre, Registrierung, KI, Sprache) ·
strikte CSP (kein Inline-Script/-Style), HSTS, `X-Frame-Options`, `nosniff` · jede Abfrage ist auf den Besitzer
beschränkt (geteilte Listen nur für Mitglieder) · Größenlimits für Anfragen, Audio und Anhänge · Anhänge werden am Inhalt
erkannt (kein HTML/SVG) und mit Sandbox-CSP ausgeliefert · TOTP mit Schutz gegen Wiederverwendung, Wiederherstellungscodes nur
als Hash · Benachrichtigungs-Aktionen über signierte, ablaufende Tokens · Audit-Log · Container: Nicht-Root, `read_only`, `cap_drop: ALL`,
`no-new-privileges`, nur an `127.0.0.1` gebunden.

## Single Sign-On

Standardmäßig ist SSO aus. Es wird aktiv, sobald `OIDC_ISSUER` (oder `OIDC_PROVIDERS`) und `PUBLIC_URL` in der `.env` stehen –
auf der Anmeldeseite erscheint dann „Mit Authentik anmelden“.

**Authentik einrichten**

1. *Applications → Providers → Create → OAuth2/OpenID Provider*
   - Client type: **Confidential**
   - Redirect URI (strict): `https://todo.example.com/api/auth/oidc/authentik/callback`
   - Signing Key: ein Zertifikat wählen (RS256; ohne Key nutzt Authentik HS256, das wird mit dem Client-Secret ebenfalls unterstützt)
   - Scopes: `openid`, `email`, `profile`
2. *Applications → Create*: Slug z. B. `todo`, Provider zuweisen. Wer sich anmelden darf, steuerst du in Authentik über
   Gruppen-/Policy-Bindings der Application.
3. In der `.env`:
   ```
   PUBLIC_URL=https://todo.example.com
   OIDC_ISSUER=https://auth.example.com/application/o/todo/
   OIDC_CLIENT_ID=<Client ID>
   OIDC_CLIENT_SECRET=<Client Secret>
   OIDC_ADMIN_GROUPS=todo-admins      # optional
   ```
   dann `docker compose up -d`. (Andere Anbieter: Redirect-URI ist immer `…/api/auth/oidc/<id>/callback`, `<id>` = `OIDC_ID`,
   Standard `authentik`; für mehrere Anbieter `OIDC_PROVIDERS` als JSON, Beispiel in `.env.example`.)

**Verhalten**

- Der Container muss die Issuer-URL erreichen können (ausgehendes HTTPS).
- Authorization-Code-Flow mit **PKCE**, `state` (an den Browser gebunden), `nonce`; das ID-Token wird per JWKS-Signatur,
  `iss`, `aud` und Ablaufzeit geprüft.
- **Freigabe-Regel bleibt:** Der allererste Benutzer überhaupt wird Admin (auch per SSO), alle weiteren SSO-Benutzer sind
  `pending`, bis ein Admin sie freigibt – außer `OIDC_AUTO_APPROVE=true` (sinnvoll, wenn Authentik den Zugang schon steuert).
  Gruppen in `OIDC_ADMIN_GROUPS` werden bei der Anmeldung zu Admins hochgestuft (nie automatisch herabgestuft).
- **Bestehendes Konto mit SSO verbinden** – zwei Wege, beide ohne automatische Verknüpfung per Name oder E-Mail
  (Schutz vor Konto-Übernahme):
  1. *Beim ersten SSO-Login:* Gibt es schon Passwort-Konten, fragt die App „Neues Konto erstellen“ oder „Mit bestehendem Konto
     verknüpfen“. Zum Verknüpfen gibst du Benutzername und Passwort des bestehenden Kontos ein (mit Sperre nach Fehlversuchen);
     danach meldest du dich direkt per SSO in genau dieses Konto an.
  2. *Später in den Einstellungen:* angemeldet unter *Einstellungen → Single Sign-On* verknüpfen und jederzeit wieder trennen.
- SSO-Konten haben zunächst kein Passwort (in den Einstellungen nachträglich festlegbar, nötig zum Trennen der letzten Verknüpfung).
- `LOCAL_AUTH_ENABLED=false` schaltet Passwort-Login und Registrierung ab (nur wirksam, wenn SSO konfiguriert ist).
- Abmelden beendet nur die Sitzung in Todo, nicht die beim Anbieter.
- Die Zwei-Faktor-Abfrage von Todo gilt für die Passwort-Anmeldung. Bei SSO entscheidet der Anbieter über den zweiten Faktor –
  aktiviere MFA also in Authentik.

## Passkeys & Zwei-Faktor

- **Passkeys** brauchen HTTPS und eine feste Domain: Die App nimmt die Domain aus `PUBLIC_URL` (sonst aus der Anfrage).
  Ein Passkey gilt nur für genau diese Domain – nach einem Domainwechsel neu anlegen. In der Android-App (WebView) werden
  Passkeys je nach Android-Version nicht unterstützt; dort Passwort + 2FA oder SSO verwenden, die App-Sperre per
  Fingerabdruck schützt zusätzlich.
- **2FA** einrichten unter *Einstellungen → Sicherheit*: QR-Code mit einer Authenticator-App scannen (Aegis, 2FAS, Google
  Authenticator, ...), Code bestätigen, Wiederherstellungscodes sicher aufbewahren. Beim Einschalten werden alle anderen
  Sitzungen abgemeldet.
- **Ausgesperrt?** Ein Wiederherstellungscode funktioniert anstelle des 6-stelligen Codes (jeder nur einmal).

## Installation

```bash
cp .env.example .env        # anpassen (Modell, VAPID_SUBJECT, ...)
docker compose up -d --build
```

Der Container lauscht nur auf `127.0.0.1:8080`. **TLS läuft über deinen nginx** – Beispiel: [`deploy/nginx.conf`](deploy/nginx.conf)
(mit SSE-Einstellungen und langen Timeouts für die KI). Ohne HTTPS funktionieren Mikrofon, Push und Installation als App nicht.

Danach `https://todo.example.com` öffnen und das erste Konto registrieren – das ist der Admin.

### Hinter Cloudflare

Liegt die Domain hinter Cloudflare, sind drei Dinge nötig:

1. **Cache umgehen:** *Caching → Cache Rules*: Hostname = deine Todo-Domain → **Bypass cache**. Sonst liefert Cloudflare nach einem
   Update bis zu Stunden alte `app.js`/`app.css` aus (erkennbar an `cf-cache-status: HIT`). Nach dem Anlegen einmal *Purge Cache*.
2. **Echte Besucher-IP** im nginx (`real_ip`, siehe Kommentar in [`deploy/nginx.conf`](deploy/nginx.conf)), damit Login-Sperre und
   Audit-Log nicht alle Besucher als dieselbe Cloudflare-IP sehen.
3. Live-Streams (SSE) laufen durch Cloudflare, solange nginx sie nicht puffert (Block ist in der Vorlage enthalten).

### Ollama & Whisper auf dem Host

Der Container erreicht den Host über `host.docker.internal`.

- **Whisper:** dein `wyoming-whisper` ist auf `0.0.0.0:10300` veröffentlicht → funktioniert direkt.
- **Ollama:** lauscht standardmäßig nur auf `127.0.0.1`. Damit der Container ihn erreicht, Ollama auf die Docker-Bridge binden
  (z. B. `OLLAMA_HOST=172.17.0.1:11434` in der systemd-Unit) – und Port 11434 per Firewall nicht nach außen öffnen.
  Alternativ `OLLAMA_URL` in `.env` anpassen. Modell laden: `ollama pull llama3.1:8b`.

## Agent-Bus-Beispiele

```bash
# Todo anlegen (Agent braucht Scope todos:write)
curl -X POST https://todo.example.com/api/agent-bus/agent/messages \
  -H "X-Agent-Key: tdo_…" -H "Content-Type: application/json" \
  -d '{"to":"todo","kind":"task","task_type":"todo.create","payload":{"title":"Backup prüfen"}}'

# Nachricht an dich (mit Push)
curl -X POST …/agent/messages -H "X-Agent-Key: tdo_…" -H "Content-Type: application/json" \
  -d '{"to":"todo","kind":"text","content":"Deploy fertig"}'

# Posteingang / Live-Stream / Ergebnis melden
curl -H "X-Agent-Key: tdo_…" "…/api/agent-bus/inbox?after_id=0"
curl -N -H "X-Agent-Key: tdo_…" …/api/agent-bus/inbox/stream
curl -X POST …/api/agent-bus/messages/ID/result -H "X-Agent-Key: tdo_…" \
  -H "Content-Type: application/json" -d '{"status":"completed","result":{"ok":true}}'
```

Agents können sich auch gegenseitig Nachrichten schicken (`"to":"<agent-name>"`, Scope `send`).

```bash
# Nachricht an ein bestimmtes Android-Gerät (Scope notify); "urgent" ignoriert die Ruhezeit
curl -X POST …/agent/messages -H "X-Agent-Key: tdo_…" -H "Content-Type: application/json" \
  -d '{"to":"todo","kind":"task","task_type":"device.notify","payload":{"device":"Pixel","title":"Server","body":"Backup fehlgeschlagen","urgent":true}}'

# Rückfrage, Antwort kommt per Knopf aus der Benachrichtigung zurück (im Posteingang des Agents)
curl -X POST …/agent/messages -H "X-Agent-Key: tdo_…" -H "Content-Type: application/json" \
  -d '{"to":"todo","kind":"task","task_type":"ask","payload":{"question":"Update jetzt einspielen?","options":["Ja","Später"]}}'

# Webhook (URL im Agent-Bereich aktivieren) – nimmt beliebiges JSON an, z. B. von GitHub
curl -X POST https://todo.example.com/api/agent-bus/hook/whk_… -H "Content-Type: application/json" -d '{"text":"Build grün"}'
```

## Später als APK

Die Oberfläche ist eine vollwertige PWA (Manifest, Service Worker, maskable Icons, HTTPS, Web-Push). Zwei einfache Wege:

1. **Bubblewrap / PWABuilder** (Trusted Web Activity): `bubblewrap init --manifest https://todo.example.com/manifest.webmanifest`
   → `bubblewrap build` ergibt eine APK/AAB, Push bleibt Web-Push.
2. **Capacitor:** `frontend/` ist reines HTML/CSS/JS ohne Build-Schritt; als `webDir` einbinden und die Server-URL
   (`server.url`) auf deine Domain setzen. Alle API-Aufrufe sind relative `/api/...`-Pfade, d. h. nur die Basis-URL
   muss bei einem lokal gebündelten Frontend zentral ergänzt werden (`api()` in `app.js`).

## Entwicklung

```bash
cd backend && pip install -r requirements-dev.txt && python -m pytest
DATA_DIR=./data COOKIE_SECURE=false FRONTEND_DIR=../frontend uvicorn app.main:app --reload
```

Struktur: `backend/app` (FastAPI + SQLite, ein Worker), `frontend/` (Vanilla-JS-PWA), `deploy/nginx.conf`.
SQLite (WAL) liegt im Volume `/data`. Die täglichen Backups liegen im selben Volume – kopiere `/data/backups` zusätzlich
auf ein anderes System (z. B. `docker cp todo:/data/backups ./todo-backups`). Wiederherstellen: Container stoppen, gewünschte
`todo-*.db` als `/data/todo.db` ins Volume legen, `todo.db-wal`/`-shm` entfernen, starten.
