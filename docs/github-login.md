# GitHub-Anmeldung und Sitzungen

Stand: 2. November 2026. Die optionale Anmeldung ist im Anwendungscode implementiert
und mit synthetischen GitHub-Antworten getestet. **Sie ist damit noch nicht auf dem
öffentlichen Dienst aktiviert.** Dazu fehlen die Registrierung einer eigenen
GitHub OAuth App und die vollständige Betreiberkonfiguration. Die Registrierung
wurde in dieser Sitzung durch die automatische Freigabeprüfung angehalten, weil
sie eine Bestätigung unmittelbar vor dieser Kontoaktion verlangt. Der bisherige
Zugangscode bleibt nutzbar.

## Welche Konten Zugriff erhalten

Die Zulassung prüft die unveränderliche numerische GitHub-Konto-ID aus der
GitHub-API. Ein bekannter Benutzername allein genügt nicht. Dadurch übernimmt ein
anderes Konto einen Zugang nicht, wenn der ursprüngliche Benutzername geändert
oder später erneut vergeben wird. Der bei jeder Anmeldung von GitHub gelieferte
aktuelle Benutzername wird nur zur Anzeige verwendet.

| Konto | Numerische GitHub-ID | Einrichtungsstand |
|---|---:|---|
| `sxba-04` | `157503913` | Über das verbundene GitHub-Konto bestätigt |
| Jonah | Noch zu bestätigen | GitHub-Benutzername und zugehörige ID fehlen |

Jonahs ID erst nach eindeutiger Zuordnung seines tatsächlichen GitHub-Kontos
aufnehmen. GitHub stellt die öffentliche ID beispielsweise unter
`https://api.github.com/users/GENAUER_BENUTZERNAME` im Feld `id` bereit. Ein Name aus
einem Commit oder ein ähnlich benanntes Suchergebnis ist kein hinreichender
Nachweis der gewünschten Person. Die Einrichtung erfordert keine Weitergabe von
GitHub-Passwörtern oder persönlichen Zugriffstoken.

Beide Autoren erhalten die Rolle `researcher`: gemeinsame Versuchsdaten lesen,
Mock-Versuche und Quellen bearbeiten, Bewertungen bearbeiten sowie die eigenen
GitHub-Sitzungen verwalten. Es gibt keine öffentliche Registrierung. Die
Freigabeliste wird ausschließlich durch den Betreiber in der geschützten
Backend-Konfiguration geändert. Zugangscodes bleiben ein unabhängiger
Betreiberzugang ohne nachgewiesene GitHub-Identität.

Die Kontozuordnung ist **keine wissenschaftliche Autorenabnahme**. Sie garantiert
weder unabhängige Bewertung A/B noch Geheimhaltung vor dem anderen Autor. Beide
Autoren sind vertrauenswürdige Mitarbeitende im selben Workspace. Die Anmeldung
ändert keine experimentelle Ticketberechtigung, keinen Fall, keine Variante
B/F/P/FP und keinen fachlichen Bewertungsmaßstab.

## OAuth App einrichten

Eine eigene, ausschließlich für diese Anmeldung genutzte GitHub OAuth App im
verifizierten Betreiberkonto registrieren. Das ist ein anderes Objekt als die
bereits installierten GitHub-Integrationen für Codex, Sonar oder Render.

- Homepage: `https://sxba-04.github.io/llm-agent-security-lab/`
- **Authorization callback URL:** `https://sxba-04.github.io/llm-agent-security-lab/`
- Keine Repository-, E-Mail-, Organisations- oder sonstigen zusätzlichen
  OAuth-Berechtigungen anfordern. Der Code sendet ausdrücklich einen leeren
  `scope`-Parameter und verwendet ausschließlich die bestätigte öffentliche
  GitHub-Kontoidentität.
- Device Flow ist für diesen Browserablauf nicht erforderlich.
- Das Client Secret ausschließlich als Render-Secret setzen. Es gehört weder ins
  Repository noch in Pages, Frontend-Buildvariablen, Screenshots oder Dokumente.

Die Rückleitung führt absichtlich auf die bestehende Pages-Startdatei mit
`?code=…&state=…`; eine zusätzliche statische Callback-Seite ist nicht nötig.
GitHub verlangt zum Austausch des einmaligen Codes das Client Secret, das nur
beim Python-Dienst liegt.

## Backend konfigurieren

Diese vier Einstellungen gemeinsam am **bestehenden** Render-Dienst setzen:

| Variable | Bedeutung |
|---|---|
| `LAB_GITHUB_CLIENT_ID` | Client ID der eigenen OAuth App |
| `LAB_GITHUB_CLIENT_SECRET` | Client Secret im geschützten Render-Konfigurationsspeicher |
| `LAB_GITHUB_REDIRECT_URI` | Exakt `https://sxba-04.github.io/llm-agent-security-lab/` |
| `LAB_GITHUB_ALLOWED_USER_IDS` | Kommagetrennte bestätigte numerische Konto-IDs beider Autoren |

Der bisherige Wert von `LAB_ACCESS_TOKEN_HASHES` bleibt erhalten. Dieser Ausbau
rotiert keinen bestehenden Zugangscode. `LAB_FRONTEND_ORIGIN` bleibt
`https://sxba-04.github.io` ohne Repository-Pfad; die OAuth-Rückleitungsadresse
enthält dagegen den vollständigen Pfad und abschließenden Slash.

Sind alle vier GitHub-Werte leer beziehungsweise nicht gesetzt, bleibt die
GitHub-Anmeldung deaktiviert. Eine unvollständige oder ungültige Konfiguration
verhindert den Dienststart. Die Rückleitung muss exakt zur konfigurierten
Frontend-Origin gehören. Wildcards, frei wählbare Rückleitungsziele,
Query-Parameter und Fragmente sind nicht erlaubt. Der Frontend-Code prüft zudem,
dass die Rückleitung seiner tatsächlichen geladenen Pages-Adresse entspricht.

Nach dem Deployment zeigt der öffentliche Endpunkt `/api/auth/config` nur
`github_enabled` und `access_code_enabled`. Er veröffentlicht keine Client Secrets,
freigegebenen IDs, Sitzungstoken oder Versuchsdaten. `/healthz` bleibt die minimale
Betriebsprüfung. Alle Datenendpunkte einschließlich Downloads bleiben geschützt.
Die beiden begrenzten OAuth-Start-/Abschlussendpunkte sind notwendige öffentliche
Anmeldefunktionen, keine Freigabe der Werkbankdaten.

## Ablauf und Schutzgrenzen

1. Der Browser erzeugt einen zufälligen PKCE-Verifier mit 256 Bit Entropie und
   sendet nur dessen SHA-256-Challenge an `/api/auth/github/start`.
2. Der Server erzeugt den zufälligen `state`, bindet ihn zehn Minuten lang an die
   Challenge und liefert eine feste GitHub-Autorisierungsadresse. Der Browser
   hält ausschließlich den vorübergehenden Verifier, `state` und Ablaufzeit in
   `sessionStorage`, damit sie die vollständige Weiterleitung überstehen.
3. Nach der Rückkehr entfernt der Browser die OAuth-Parameter aus der sichtbaren
   Adresse, prüft den einmaligen lokalen Zustand und übermittelt Code, `state`
   und Verifier an `/api/auth/github/complete`. Er entfernt den vorübergehenden
   Anmeldeeintrag auch bei Fehlern. Eine Referrer-Regel verhindert die Weitergabe
   der Callback-Parameter beim Laden weiterer Ressourcen.
4. Der Server prüft Zustand und PKCE, verbraucht den Anmeldevorgang vor dem
   ersten Provideraufruf und tauscht den Code ausschließlich beim festen
   GitHub-HTTPS-Endpunkt aus. Weiterleitungen auf andere Ziele werden abgelehnt.
   Anschließend fragt er `https://api.github.com/user` ab und prüft die numerische
   Freigabeliste. Der GitHub-Token wird weder gespeichert noch zum Browser
   zurückgegeben.
5. Erst nach erfolgreicher Prüfung entsteht ein eigener zufälliger
   Anwendungstoken. Der Browser hält ihn nur im Arbeitsspeicher; der Server hält
   nur seinen Hash mit Identität und Ablaufzeit. Alle bisherigen Host-/Origin-,
   Größen- und Mutationstokenprüfungen bleiben wirksam.

Es gibt keine Abhängigkeit von Drittanbieter-Cookies oder Popup-Openern. GitHub-
und Anwendungstoken stehen niemals in URLs, `localStorage` oder `sessionStorage`.
Nur das kurzlebige PKCE-Material liegt für die Weiterleitung vorübergehend im
Sitzungsspeicher. Die normale Eingabe eines Zugangscodes verwendet weiterhin
keinen persistenten Browserspeicher.

Vor der Anmeldung verlangen die beiden POST-Endpunkte die exakt konfigurierte
Frontend-Origin und JSON; ihre Anfragegröße ist auf 4 KiB begrenzt. Anmeldeversuche
sind pro transportseitiger Client-Adresse und global begrenzt; beliebige
`X-Forwarded-For`-Werte können diese Grenze nicht umgehen. Hinter einem Reverse
Proxy kann eine transportseitige Adresse für mehrere Nutzer gelten. Höchstens
vier GitHub-Austauschvorgänge laufen gleichzeitig. Warteschlangen, Antworten,
Zeitlimits und Sitzungsanzahl sind begrenzt.

## Abmelden und Sitzungen beenden

Eine GitHub-Sitzung gilt höchstens acht Stunden ab der Anmeldung, ohne automatische
Verlängerung. Im Kontomenü kann jeder Autor seine eigenen Sitzungen anzeigen und
einzelne Sitzungen beenden. Sitzungen des anderen Kontos sind dort weder sichtbar
noch widerrufbar. Maximal acht Sitzungen pro Konto bleiben aktiv; eine neunte
Anmeldung beendet die älteste Sitzung desselben Kontos, damit häufiges Neuladen
nicht zu einer längerfristigen Aussperrung führt.

**Abmelden** löscht den Browserzustand sofort und widerruft zusätzlich die
Serversitzung. Falls die Serverantwort ausbleibt, weist die Oberfläche darauf hin:
Die lokale Abmeldung ist erfolgt, der serverseitige Widerruf ist dann nicht
bestätigt. Die Sitzung kann nach erneuter Anmeldung im Kontomenü beendet werden
und läuft spätestens nach acht Stunden ab.

Das Neuladen der Seite löscht den nur im Arbeitsspeicher gehaltenen
Anwendungstoken. Die erneute GitHub-Anmeldung ist dann erforderlich; eine noch
aktive GitHub-Sitzung kann den Kontowechsel beim Anbieter vereinfachen. Der Server
speichert Anwendungssitzungen bewusst nur im Prozessspeicher. Ein Dienstneustart
oder Deployment widerruft daher alle GitHub-Sitzungen und offenen
Anmeldevorgänge. Auf einer tatsächlich eingerichteten persistenten Disk gespeicherte
Versuchsdaten bleiben davon getrennt. Der Zugangscode bleibt bei unveränderter
Hash-Konfiguration weiterhin gültig.

Die Anwendung wiederholt fehlgeschlagene Schreibaktionen oder OAuth-Austausche
nicht automatisch. Nach einem Fehler die Anmeldung oder gewünschte Bedienaktion
bewusst neu auslösen.

## Prüfung und Aktivierung

Die Python-Prüfungen verwenden ausschließlich synthetische Providerantworten.
Sie prüfen unter anderem PKCE, falschen oder wiederverwendeten Zustand,
Zeitablauf, unerlaubte Konto-ID, Kontoumbenennung, Origin, Größenbegrenzung,
Providerfehler, Sitzungswiderruf, kontoübergreifende Zugriffsversuche und die
unveränderte Zugangscode-Anmeldung. Die Frontend-Prüfung kontrolliert den
Weiterleitungs- und Rückkehrablauf einschließlich Löschung der Callback-Parameter
und temporären Zustandsdaten. Dies sind keine behaupteten erfolgreichen
Anmeldungen mit den echten Konten.

Nach vollständiger Konfiguration sind zusätzlich die echte Anmeldung beider
Autoren, die Ablehnung eines nicht freigegebenen Kontos, Abmeldung/Widerruf sowie
Zugriff auf geschützte Daten zu prüfen. Ein erfolgreich gebautes Frontend oder
`github_enabled: true` allein ersetzt diese Prüfung nicht. Die Registrierung und
Live-Aktivierung sind im vorliegenden Stand noch offen.

Die Implementierung und ihre synthetischen Tests wurden mit Codex unterstützt.
Die wissenschaftliche Autorenabnahme und reale unabhängige Bewertungen werden
dadurch nicht ersetzt.

## Offizielle Referenz

[GitHub: Authorizing OAuth apps](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps)
– Web Application Flow, `state`, PKCE mit S256, Rückleitungsadresse und erneute
Abfrage der Kontoidentität bei jeder Anmeldung. Die Referenz wurde bei der
Implementierung am 2. November 2026 abgerufen.
