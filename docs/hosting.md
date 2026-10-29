# Vollständige Werkbank im Browser

Stand: 29. Oktober 2026. Die Hosting-Konfiguration ist vorbereitet. Eine Datei im Repository ist kein Nachweis eines bereits bereitgestellten Backends oder einer erfolgreich veröffentlichten Website.

## Aufbau und Funktionsumfang

Nach abgeschlossener Bereitstellung liefert GitHub Pages die gebaute React-Oberfläche unter `https://sxba-04.github.io/llm-agent-security-lab/`. Die Oberfläche spricht nach Eingabe eines Zugangscodes mit einem eigenen Python-Dienst über HTTPS. Dort laufen derselbe Versuchskern, die PDF-Extraktion, die Archivierung und die Bewertung wie in der lokalen Werkbank. Es wird keine zweite Versuchsauswertung in JavaScript implementiert.

GitHub Pages führt selbst keinen Python-Server aus. Für die vollständige Nutzung ohne lokalen Prozess braucht es deshalb **zusätzlich den laufenden Backend-Dienst und dauerhaften Speicher**. Die Oberfläche bleibt im Mock-Modus; diese Veröffentlichung aktiviert weder echte Modellaufrufe noch ein API-Budget.

| Bestandteil | Betrieb und Zugriff |
|---|---|
| GitHub Pages | Öffentlich erreichbare Anmeldeseite und statische Frontend-Dateien. Enthält keine Zugangscodes, Workspace-Dateien oder privaten Bewertungen. |
| Python-Backend | Datenzugriff und Änderungen erst mit gültigem Bearer-Zugangscode. `/healthz` ist eine öffentliche, minimale Betriebsprüfung. |
| Persistenter Workspace | Gemeinsame Kampagnen, PDF-Originale, bestätigte Extraktionen, Bewertungen und Provenienz für beide Autoren. |
| Lokale Werkbank | Bleibt mit dem bisherigen Startbefehl und eigenen lokalen Daten nutzbar. Lokale und gehostete Daten werden nicht automatisch synchronisiert. |

## 1. Backend bereitstellen

`render.yaml` beschreibt eine mögliche Bereitstellung bei Render. **Das Importieren und Bestätigen des Blueprints erstellt kostenpflichtige Ressourcen.** Preis, Account und Speicher vor dieser Bestätigung prüfen. Die Vorlage reserviert eine Instanz in Frankfurt mit dem Plan `1c-2g` und einer 1-GB-Disk. Diese Ressourcen werden durch einen Git-Commit allein nicht angelegt. Ein kostenloser Dienst ohne persistente Disk ist für die vorhandenen Belegdateien ungeeignet.

1. Render mit dem eigenen GitHub-Konto verbinden und diesem Repository Zugriff geben. Nicht nur die öffentliche Repository-URL importieren: diese Alternative unterstützt keine automatischen Deployments.
2. Den Blueprint des Repositorys importieren und die Kosten-/Ressourcenübersicht prüfen. Der Branch ist `main`; automatische Updates sind auf erfolgreiche CI-Prüfungen eingestellt.
3. Zwei voneinander unabhängige Zugangscodes lokal erzeugen und ihre SHA-256-Hashes als `LAB_ACCESS_TOKEN_HASHES` konfigurieren. Die Hashes werden mit einem Komma getrennt. Die echten Codes gehören ausschließlich zu den jeweiligen Autoren.
4. Die persistente Disk muss unter `/var/data` eingehängt sein. Der Workspace liegt unter `/var/data/security-lab`.
5. Nach erfolgreichem Backend-Deployment dessen HTTPS-Adresse übernehmen. `/healthz` muss erreichbar sein; `/api/cases` muss ohne Zugangscode mit HTTP 401 antworten.

Die Vorlage verwendet das unveränderte Python-Lockfile. Der Hosting-Start erfolgt durch `python -m security_lab.hosted_cli`; der übliche lokale Launcher wird nicht für eine öffentliche Freigabe umkonfiguriert. Es bleibt bei einer Instanz und einem Worker. Mehrere Worker oder horizontale Skalierung sind mit den vorhandenen In-Process-Sperren und der dateibasierten Speicherung nicht unterstützt.

### Zugangscodes ohne Speicherung im Repository erzeugen

Jeder Autor kann diesen Befehl auf seinem eigenen Rechner ausführen. Er erzeugt einen zufälligen Code mit 256 Bit Entropie und den dazugehörigen Hash:

```powershell
uv run python -c "import hashlib,secrets; code=secrets.token_urlsafe(32); print('Persoenlicher Zugangscode:',code); print('Server-Hash:',hashlib.sha256(code.encode('ascii')).hexdigest())"
```

Den Code unmittelbar in einem Passwortmanager speichern; nur den Server-Hash zur Einrichtung weitergeben. Keine Codes in Git-Dateien, Screenshots, Pull Requests, Chatnachrichten, GitHub-Variablen oder Frontend-Builds eintragen. Der Befehl enthält selbst keinen Zugangscode, aber seine Terminalausgabe ist vertraulich. Keine selbst gewählten kurzen Passwörter verwenden.

Der Browser hält den eingegebenen Code nur im Arbeitsspeicher. Abmelden oder Neuladen erfordert eine erneute Eingabe; es gibt keine Speicherung in `localStorage` oder `sessionStorage`. PDF- und Archivdownloads übertragen die Authentifizierung als Header, niemals als URL-Parameter.

Bei Verlust oder vermuteter Offenlegung einen neuen Code erzeugen, den alten Hash aus `LAB_ACCESS_TOKEN_HASHES` entfernen und die Backend-Konfiguration neu bereitstellen. Ein Frontend-Neubau ist für die Rotation nicht nötig.

### Backend-Einstellungen

| Variable | Wert / Bedeutung |
|---|---|
| `LAB_PUBLIC_ORIGIN` | Eigene HTTPS-Origin ohne Pfad. Auf Render kann sie entfallen; dann wird `RENDER_EXTERNAL_URL` verwendet. Bei eigener Domain explizit setzen. |
| `LAB_FRONTEND_ORIGIN` | `https://sxba-04.github.io` – ohne Repository-Pfad und ohne abschließenden Slash. |
| `LAB_ACCESS_TOKEN_HASHES` | Kommagetrennte SHA-256-Hashes der zufälligen Zugangscodes, im Backend-Secret-Speicher konfigurieren. |
| `LAB_WORKSPACE` | `/var/data/security-lab`, innerhalb der persistenten Disk. |
| `PORT` | Vom Hostinganbieter bereitgestellter HTTP-Port hinter dessen HTTPS-Proxy. |

Die Origin-/Hostprüfung bleibt aktiv. CORS erlaubt ausschließlich die konfigurierte Frontend-Origin; auch Fehlermeldungen und Preflight-Anfragen müssen diesen Vertrag erfüllen. Die Browser-Anmeldung verwendet keine Drittanbieter-Cookies. Der Hoster beendet TLS vor dem Python-Dienst; die öffentliche HTTPS-Origin wird explizit validiert, statt beliebigen weitergeleiteten Headern zu vertrauen.

## 2. GitHub Pages mit dem Backend verbinden

1. Im Repository unter **Settings → Secrets and variables → Actions → Variables** die Repository-Variable `LAB_API_BASE_URL` auf die öffentliche Backend-Origin setzen, beispielsweise `https://DEIN-DIENST.onrender.com`. **Keinen Zugangscode hinzufügen.** Die URL darf keinen API-Pfad, Benutzerinformationen, Query oder Fragment enthalten.
2. Unter **Settings → Pages → Build and deployment → Source** **GitHub Actions** auswählen. HTTPS aktiviert lassen.
3. Unter **Actions → Hosted workbench and Pages → Run workflow** den Branch `main` starten.
4. Den erfolgreichen Build und das `github-pages`-Deployment prüfen; anschließend die veröffentlichte URL öffnen und mit dem eigenen Code anmelden.

Ohne `LAB_API_BASE_URL` prüft der Workflow weiterhin den Hosted-Build und die Browserintegration, veröffentlicht aber bewusst keine funktionslose Website. Der Jobbericht nennt die fehlende Einrichtung. Ein beliebiger Platzhalter darf daher nicht als Produktionswert eingetragen werden. Die Repository-Variable ist öffentliches Konfigurationswissen, kein Geheimnis.

Nur `frontend/dist` wird zu Pages übertragen. Der Workflow veröffentlicht weder Python-Quellverzeichnisse noch den Workspace. Pull Requests führen die Prüfungen aus, veröffentlichen aber nichts. Das Deployment hat auf `main` begrenzte Pages-/OIDC-Rechte; Test- und Buildjobs besitzen nur Lesezugriff auf Repository-Inhalte. Die verwendeten GitHub Actions sind auf konkrete Commit-SHAs festgelegt.

## 3. Automatische Updates und Betrieb

Neue Änderungen auf `main` lösen den Frontend-Workflow aus. Das Backend ist über die GitHub-Anbindung ebenfalls mit `main` verbunden und aktualisiert sich nach erfolgreichen CI-Prüfungen. Beide Dienste veröffentlichen getrennt; sie wechseln nicht atomar im selben Moment. API-Änderungen müssen deshalb während der Übergangsphase mit der jeweils anderen Version kompatibel bleiben.

Die persistente Render-Disk bleibt bei einem Neustart oder Redeployment erhalten. Während der Umstellung gibt es eine kurze Unterbrechung. Ein laufender Mock-Versuch kann dabei abgebrochen werden. Vor geplanten Updates Versuche beenden und wichtige Archive herunterladen. Ein unterbrochener Lauf wird anhand seiner Belege als solcher behandelt und nicht automatisch wiederholt. Nach einem Backend-Neustart die Seite neu laden und erneut anmelden, wenn das Sitzungstoken nicht mehr gültig ist.

Die beiden Zugangscodes erlauben denselben gemeinsamen Arbeitsbereich. Sie sind keine Rollenverwaltung: beide Autoren können Kampagnen und Bewertungsansichten öffnen. Die bestehende Trennung in Bewertung A/B unterstützt den Arbeitsablauf, garantiert aber keine technische Geheimhaltung gegenüber dem jeweils anderen Autor. Für unabhängige Urteile die getrennten Bewertungsansichten und organisatorischen Regeln weiter einhalten.

Nur synthetische Versuchsdaten verwenden. Regelmäßig vollständige Kampagnenarchive exportieren und die Wiederherstellung prüfen; eine persistente Disk allein ist keine vollständige Sicherungsstrategie. Speicherverbrauch überwachen. Beim Wechsel des Hostinganbieters PDF-Originale, Bewertungen und Provenienz gemeinsam mit den Laufdaten übernehmen.

## Prüfung der Hosting-Variante

Die CI baut den tatsächlichen Hosted-Modus unter `/llm-agent-security-lab/` und verbindet ihn im Browser mit einem separaten HTTPS-Testbackend. Die selbstsignierten Testzertifikate und der öffentliche synthetische Testcode gelten ausschließlich für diese wegwerfbare Testumgebung; produktive TLS-Prüfungen werden dadurch nicht abgeschaltet.

Geprüft werden Anmeldung/Abmeldung, Ablehnung ohne Code, fehlende Token-Speicherung, PDF-Download und -Import samt Bestätigung, Mock-Versuch und authentifizierter Archivdownload. Browserdiagnosen liegen als kurzzeitig aufbewahrtes CI-Artefakt vor. Ein erfolgreicher Test der Testumgebung ersetzt die abschließende Prüfung der tatsächlich veröffentlichten Adresse nicht.

Lokaler Aufruf des Hosted-Browsertests (OpenSSL und Playwright-Chromium erforderlich):

```powershell
uv sync --locked --extra web --group dev
cd frontend
npm.cmd ci
$env:VITE_HOSTED = "true"
$env:VITE_API_BASE_URL = "https://127.0.0.1:8876"
npm.cmd run build -- --base /llm-agent-security-lab/ --outDir dist-hosted
npm.cmd run test:e2e:hosted
Remove-Item Env:VITE_HOSTED
Remove-Item Env:VITE_API_BASE_URL
```

Der Testbuild liegt separat in `frontend/dist-hosted`; ein vorhandener lokaler Build in `frontend/dist` bleibt erhalten. Die Testserver starten auf reservierten Loopback-Ports; sie verwenden einen eigenen temporären Workspace und greifen nicht auf lokale Forschungsdaten zu.

## Offizielle Grundlagen

- [GitHub Pages: statisches Hosting](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
- [GitHub Pages mit eigenen Workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [Render-Webservices und Git-Anbindung](https://render.com/docs/web-services)
- [Persistente Disks und Deploymentgrenzen](https://render.com/docs/disks)
- [Render-Blueprint-Spezifikation](https://render.com/docs/blueprint-spec)

Die Bereitstellung ändert die Erreichbarkeit, nicht die experimentellen Varianten B/F/P/FP oder deren Auswertung. Die Hosting-Änderungen und Tests wurden mit Codex unterstützt; fachliche Autorenabnahme und ein geprüfter echter API-Pilot werden dadurch nicht ersetzt.
