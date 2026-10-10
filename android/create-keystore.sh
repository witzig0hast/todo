#!/usr/bin/env bash
# Erzeugt einen dauerhaften Signierschlüssel für die Todo-APK und gibt die Werte für die GitHub-Secrets aus.
# Mit demselben Schlüssel signierte APKs lassen sich ohne Deinstallation aktualisieren.
set -euo pipefail

OUT="${1:-todo-release.jks}"
ALIAS="todo"
if [ -e "$OUT" ]; then echo "Datei $OUT existiert bereits – abgebrochen." >&2; exit 1; fi

PASS="$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 24)"
keytool -genkeypair -v -keystore "$OUT" -storetype PKCS12 -alias "$ALIAS" -keyalg RSA -keysize 4096 -validity 36500 \
  -storepass "$PASS" -keypass "$PASS" -dname "CN=Todo, O=Self-hosted" >/dev/null

echo
echo "Keystore: $OUT   (SICHER AUFBEWAHREN, NICHT einchecken – Verlust = keine Updates mehr)"
echo
echo "Lege diese vier Secrets an (GitHub → Settings → Secrets and variables → Actions):"
echo "  ANDROID_KEYSTORE_BASE64   = $(base64 -w0 "$OUT" 2>/dev/null || base64 "$OUT" | tr -d '\n')"
echo "  ANDROID_KEYSTORE_PASSWORD = $PASS"
echo "  ANDROID_KEY_ALIAS         = $ALIAS"
echo "  ANDROID_KEY_PASSWORD      = $PASS"
