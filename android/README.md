# Todo – Android-App

Native Hülle um die Web-App (WebView) mit **eigener Hintergrundverbindung für Nachrichten**. Jedes Gerät registriert sich
mit einem eigenen Token; du kannst Nachrichten gezielt an ein Gerät oder an alle senden – ohne Google-Dienste (kein FCM).

## Was die App kann

- Lädt deine Todo-Installation (Adresse beim ersten Start, oder fest eingebaut).
- **Nachrichten direkt aufs Gerät:** Erinnerungen, Agent-Bus-Meldungen, Freigaben und manuell gesendete Nachrichten erscheinen
  als Benachrichtigung. Beim Antippen öffnet sich die passende Seite.
- **Gezielt pro Gerät:** In der Web-App unter *Einstellungen → Geräte* (Nachricht an ein Gerät / an alle) oder per Agent Bus
  (`device.notify`, Scope `notify`).
- **Offline-Zeiten:** Der Server hält Nachrichten pro Gerät vor und liefert sie beim nächsten Verbinden nach (bis 30 Tage,
  bestätigte nach 7 Tagen gelöscht).
- **Homescreen-Widget „Todo – Heute“:** heute fällige und überfällige Aufgaben abhaken, mit „+“ neue anlegen (Schnelleingabe
  mit Datums-/Tag-Erkennung, optional per Spracheingabe des Handys). Mit aktiver App-Sperre zeigt das Widget nur Zahlen.
- **App-Shortcuts** (lange aufs App-Symbol drücken): Neue Aufgabe, Diktieren (öffnet die App mit Whisper-Aufnahme), Heute, Suchen.
- **Schnelleinstellungs-Kachel „Neue Aufgabe“:** Statusleiste herunterziehen → Bearbeiten → Kachel hinzufügen.
- **Updates über deinen Server:** Neue Versionen meldet die App selbst („Update verfügbar“) und installiert sie nach Bestätigung.
- Mikrofon für die Spracheingabe (Whisper), SSO über Authentik/andere Anbieter (läuft im selben WebView),
  Start nach Neustart, Zurück-Taste, Offline-Seite mit „Erneut versuchen“ / „Server ändern“.

## APK bauen (GitHub Actions, empfohlen)

1. Repository → **Actions → Android APK → Run workflow**.
   - *server_url* (optional): fest einbauen, z. B. `https://todo.example.com` – dann entfällt die Eingabe beim Start.
   - *release*: zusätzlich als GitHub-Release veröffentlichen.
2. Nach ca. 5 Minuten: im Lauf unter **Artifacts → todo-android** die APK herunterladen (oder im Release).
3. Auf dem Handy installieren (einmalig „Installation aus unbekannten Quellen“ für den Browser/Dateimanager erlauben).

Ein Tag `android-v…` (z. B. `git tag android-v1.0.0 && git push --tags`) baut ebenfalls und legt ein Release an.

### Dauerhafter Signierschlüssel (damit Updates ohne Deinstallation gehen)

Ohne eigenen Schlüssel wird mit dem Debug-Schlüssel signiert; dieser ist bei jedem CI-Lauf anders → Updates nur nach
Deinstallation. Einmalig:

```bash
./android/create-keystore.sh      # gibt vier Werte aus
```

Die vier Werte als **Repository-Secrets** anlegen (`ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`,
`ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`). Die Keystore-Datei sicher aufbewahren (nicht einchecken).

## Updates verteilen

Updates lassen sich nur installieren, wenn **alle Versionen mit demselben Schlüssel signiert** sind – also zuerst den
dauerhaften Signierschlüssel einrichten (oben). Dann gibt es zwei Wege:

1. **Von Hand:** APK aus GitHub Actions herunterladen und in der Web-App unter *Admin → Android-App → APK hochladen*
   bereitstellen (Version wird aus dem Dateinamen `todo-1.0.N.apk` gelesen).
2. **Automatisch aus der CI:** In der Web-App als Admin ein API-Token mit Recht „schreiben“ erzeugen
   (*Einstellungen → Integrationen & API-Tokens*) und zwei weitere Repository-Secrets anlegen:
   `TODO_SERVER_URL` (z. B. `https://todo.example.com`) und `TODO_UPLOAD_TOKEN` (das Token). Jeder Build lädt die APK dann
   selbst hoch.

Die App fragt höchstens alle 6 Stunden nach, zeigt eine Benachrichtigung und – in *Einstellungen → Geräte* – den Knopf
„Update installieren“. Beim ersten Mal fragt Android, ob Todo Apps installieren darf. Die Datei wird vor der Installation
per SHA-256 geprüft. nginx: der Block für `/api/app/android` aus [`deploy/nginx.conf`](../deploy/nginx.conf) erlaubt größere Uploads.

Jeder CI-Lauf zeigt in der Zusammenfassung (und im Release) den SHA-256-Fingerabdruck des Signatur-Zertifikats.

## Lokal bauen

Voraussetzungen: JDK 17, Android SDK (API 35). Dann:

```bash
cd android
./gradlew assembleRelease -PserverUrl=https://todo.example.com     # -PserverUrl optional
# → app/build/outputs/apk/release/app-release.apk
```

Oder `android/` in Android Studio öffnen.

## So funktioniert die Nachrichtenzustellung

1. Nach der Anmeldung registriert die Web-Oberfläche das Gerät (`POST /api/devices/register`) und übergibt den
   einmalig angezeigten **Geräte-Token** an die App (`window.TodoAndroid`, nur für die eigene Server-Origin).
2. Ein Vordergrunddienst hält `GET /api/devices/stream` (SSE, `Authorization: Bearer <Token>`) offen, zeigt jede Nachricht an und
   bestätigt sie (`POST /api/devices/messages/{id}/ack`). Bei Verbindungsabbruch wird mit Backoff neu verbunden, sofort wenn
   das Netz zurückkehrt.
3. Wird das Gerät in der Web-App entfernt, beendet sich der Dienst; beim nächsten Öffnen registriert sich die App neu.
   Beim Abmelden in der App wird das Gerät serverseitig entfernt.

### Wichtig für zuverlässige Zustellung

Android schränkt Hintergrundverbindungen im Ruhezustand (Doze) ein. Für sofortige Zustellung bei ausgeschaltetem
Bildschirm: **Einstellungen → Geräte → „Akku-Optimierung ausschalten“** (in der App), und bei manchen Herstellern
(Xiaomi, Samsung, Huawei, OnePlus) zusätzlich „Autostart“ erlauben und die App aus dem Energiesparen ausnehmen.
Die dauerhafte Benachrichtigung „Verbindung“ ist von Android vorgeschrieben; sie lässt sich in den
Benachrichtigungs-Einstellungen der App stumm/minimiert halten.

## Sicherheit

- Nur `https://` (kein Klartext). Navigation im WebView nur zum eigenen Server und zu Anbietern, auf die der Server
  weiterleitet (SSO); alles andere öffnet sich im Browser.
- Die App-Schnittstelle wird ausschließlich für die eigene Origin eingebunden; der Geräte-Token liegt im privaten App-Speicher
  (Backup ist ausgeschaltet) und kann in der Web-App jederzeit widerrufen werden.
- Mikrofonzugriff nur für die eigene Origin und nach Android-Berechtigungsabfrage.
