# Kostenlose Testwerkbank im Browser

Stand: 29. Oktober 2026. Das Team hat ausdrücklich die kostenlose Umgebung ohne Kosten oder Buchungen gewählt. Die Hosting-Konfiguration ist dafür vorbereitet. Eine Datei im Repository ist kein Nachweis eines bereits bereitgestellten Backends oder einer erfolgreich veröffentlichten Website.

## Aufbau und Funktionsumfang

Nach abgeschlossener Bereitstellung liefert GitHub Pages die gebaute React-Oberfläche unter `https://sxba-04.github.io/llm-agent-security-lab/`. Die Oberfläche spricht nach Eingabe eines Zugangscodes mit einem eigenen Python-Dienst über HTTPS. Dort laufen derselbe Versuchskern, die PDF-Extraktion, die Archivierung und die Bewertung wie in der lokalen Werkbank. Es wird keine zweite Versuchsauswertung in JavaScript implementiert.

GitHub Pages führt selbst keinen Python-Server aus. Für die Nutzung ohne lokalen Prozess braucht es deshalb **zusätzlich den laufenden Backend-Dienst**. Die gewählte kostenlose Testumgebung verwendet einen flüchtigen Workspace: **Hochgeladene PDFs, Versuche und Bewertungen gehen beim Ruhezustand, Neustart oder Deployment verloren.** Benötigte Archive vorher herunterladen und wichtige Studienbelege außerhalb dieser Umgebung sichern. Die Oberfläche bleibt im Mock-Modus; diese Veröffentlichung aktiviert weder echte Modellaufrufe noch ein API-Budget.

| Bestandteil | Betrieb und Zugriff |
|---|---|
| GitHub Pages | Öffentlich erreichbare Anmeldeseite und statische Frontend-Dateien. Enthält keine Zugangscodes, Workspace-Dateien oder privaten Bewertungen. |
| Python-Backend | Datenzugriff und Änderungen erst mit gültigem Bearer-Zugangscode. `/healthz` ist eine öffentliche, minimale Betriebsprüfung. |
| Flüchtiger Test-Workspace | Gemeinsame Kampagnen, PDF-Originale, bestätigte Extraktionen, Bewertungen und Provenienz für beide Autoren, nur bis zum Zurücksetzen des Dienstes. Keine dauerhafte Belegablage. |
| Lokale Werkbank | Bleibt mit dem bisherigen Startbefehl und eigenen lokalen Daten nutzbar. Lokale und gehostete Daten werden nicht automatisch synchronisiert. |

## 1. Backend bereitstellen

`render.yaml` beschreibt einen einzelnen Python-Webservice `llm-agent-security-lab-demo-api` in Frankfurt mit `plan: free`, ohne Disk, Datenbank oder zusätzlichen Worker. Der Workspace liegt unter `/tmp/security-lab-demo`; `LAB_STORAGE_MODE=ephemeral` aktiviert den Speicherhinweis. Ein Git-Commit allein legt keine Ressource an. Alternativ kann derselbe einzelne Dienst mit diesen Einstellungen direkt über die Render-Verwaltung angelegt werden; dann ist die Dienstkonfiguration dort die Quelle der tatsächlichen Einstellungen, bis bewusst eine Blueprint-Verwaltung eingerichtet wird.

**Kostenfreiheit vor Erstellung prüfen:** Den vom Nutzer bestätigten Render-Workspace verwenden, den Hobby-Workspace und den Free-Compute-Plan kontrollieren und sicherstellen, dass kein Zahlungsmittel hinterlegt ist. Der Hobby-Workspace allein macht kostenpflichtige Serverressourcen nicht kostenlos. Bei einer Zahlungsaufforderung, kostenpflichtigen Ressource oder unklarer Abrechnung anhalten; nichts buchen oder automatisch hochstufen. Ohne Zahlungsmittel pausiert Render beim Überschreiten der kostenlosen Transfergrenze den Dienst und beim Ausschöpfen der Build-Minuten weitere Builds. Die Freikontingente sind kein Auftrag, anschließend Ressourcen zuzukaufen.

1. Render mit dem eigenen GitHub-Konto verbinden und diesem Repository Zugriff geben. Nicht nur die öffentliche Repository-URL importieren: diese Alternative unterstützt keine automatischen Deployments.
2. Die oben genannten Free-Einstellungen und die Kosten-/Ressourcenübersicht prüfen. Der Branch ist `main`; automatische Updates auf erfolgreiche CI-Prüfungen einstellen. Beim Blueprint entspricht dies `autoDeployTrigger: checksPass`. Keine Disk, Datenbank, kostenpflichtigen Zusatzdienste oder Vorschauumgebungen anlegen.
3. Für jeden Autor einen unabhängigen Zugangscode lokal erzeugen und dessen SHA-256-Hash als `LAB_ACCESS_TOKEN_HASHES` konfigurieren. Ein erster Code genügt zur Einrichtung; weitere Hashes können später kommagetrennt ergänzt werden. Die echten Codes gehören ausschließlich zu den jeweiligen Autoren.
4. `LAB_WORKSPACE=/tmp/security-lab-demo` und `LAB_STORAGE_MODE=ephemeral` setzen. Der Dienst erstellt seine Arbeitsverzeichnisse selbst; es wird keine persistente Disk eingehängt.
5. Nach erfolgreichem Backend-Deployment dessen HTTPS-Adresse übernehmen. `/healthz` muss erreichbar sein; `/api/cases` muss ohne Zugangscode mit HTTP 401 antworten. Die authentifizierte `/api/health`-Antwort muss `storage_mode: ephemeral` und `mode: mock` enthalten. Anschließend die Pages-Verbindung und den Speicherhinweis tatsächlich im Browser prüfen.

Die Vorlage verwendet das unveränderte Python-Lockfile. Der Hosting-Start erfolgt durch `python -m security_lab.hosted_cli`; der übliche lokale Launcher wird nicht für eine öffentliche Freigabe umkonfiguriert. Es bleibt bei einer Instanz und einem Worker. Mehrere Worker oder horizontale Skalierung sind mit den vorhandenen In-Process-Sperren und der dateibasierten Speicherung nicht unterstützt.

Die Free-Instanz stellt 512 MB RAM bereit. Das Labor lädt keine Modellgewichte; ein gewöhnlicher Mock-Ablauf ist deshalb ein sinnvoller Test für diese kleine Instanz. Das ist noch kein Nachweis, dass beliebig große oder parallele PDF-Importe unter dieser Speichergrenze gelingen. Die tatsächliche Ressourcennutzung nach Bereitstellung prüfen und Fehler offen ausweisen; keine automatische kostenpflichtige Vergrößerung.

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
| `LAB_WORKSPACE` | `/tmp/security-lab-demo` für die gewählte kostenlose Testumgebung. Absoluter Pfad, keine dauerhafte Speicherung. |
| `LAB_STORAGE_MODE` | `ephemeral` für die kostenlose Testumgebung; nur `ephemeral` und `persistent` sind gültig. Ohne Angabe gilt `persistent`. Die Einstellung beschreibt den vorgesehenen Speicherlebenszyklus; sie richtet selbst keine Disk ein und löscht keine Dateien. |
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

Nach der oben beschriebenen Einrichtung lösen neue Änderungen auf `main` den Frontend-Workflow aus. Das über GitHub angebundene Backend aktualisiert sich nach erfolgreichen CI-Prüfungen. Beide Dienste veröffentlichen getrennt; sie wechseln nicht atomar im selben Moment. API-Änderungen müssen deshalb während der Übergangsphase mit der jeweils anderen Version kompatibel bleiben. Diese Beschreibung des Zielbetriebs ersetzt nicht die Prüfung der tatsächlich eingerichteten Anbindung.

Der kostenlose Dienst schläft nach 15 Minuten ohne eingehenden Verkehr ein; die nächste Verbindung kann etwa eine Minute zum Aufwecken benötigen. Ein offen benutzter Browser erzeugt reguläre Anfragen. Es wird kein zusätzlicher Keep-alive-Dienst eingerichtet, um die Free-Grenzen zu umgehen.

Bei Ruhezustand, Neustart oder Deployment gehen die Dateien des flüchtigen Workspace verloren. Das betrifft auch bestätigte PDF-Texte, Bewertungen und mögliche Unterbrechungsnachweise. Vor geplanten Updates Versuche beenden und benötigte Archive herunterladen. Die Oberfläche zeigt auf allen Arbeitsseiten einen Hinweis. Ein laufender Mock-Versuch kann abgebrochen werden und wird nicht automatisch wiederholt. Falls die Belege gelöscht wurden, kann daraus kein vollständiger Lauf rekonstruiert oder als Erfolg ausgegeben werden. Nach einem Backend-Neustart die Seite neu laden und erneut anmelden, wenn das Sitzungstoken nicht mehr gültig ist.

Die konfigurierten Zugangscodes erlauben denselben gemeinsamen Arbeitsbereich. Sie sind keine Rollenverwaltung: beide Autoren können Kampagnen und Bewertungsansichten öffnen. Die bestehende Trennung in Bewertung A/B unterstützt den Arbeitsablauf, garantiert aber keine technische Geheimhaltung gegenüber dem jeweils anderen Autor. Für unabhängige Urteile die getrennten Bewertungsansichten und organisatorischen Regeln weiter einhalten.

Nur synthetische Versuchsdaten verwenden. Benötigte vollständige Kampagnenarchive rechtzeitig exportieren und die Wiederherstellung lokal prüfen. Separat hochgeladene Quellen ohne Kampagnenzuordnung müssen zusätzlich außerhalb der Umgebung vorhanden sein. Der kostenlose Dienst darf nicht die einzige Ablage wichtiger Studienbelege sein. Beim Wechsel des Hostinganbieters PDF-Originale, Bewertungen und Provenienz gemeinsam mit den Laufdaten übernehmen.

### Optional später: dauerhafte Speicherung

Dauerhafte gemeinsame Belege können mit einer separat freigegebenen kostenpflichtigen Instanz und Disk oder mit einer gesondert implementierten externen Speicherung betrieben werden. Dafür sind Kosten, Datenmigration und Wiederherstellung neu zu prüfen. Bei einer Render-Disk könnte der Workspace beispielsweise unter `/var/data/security-lab` liegen und `LAB_STORAGE_MODE=persistent` gelten. Die bloße Umschaltung der Variablen macht den Speicher nicht dauerhaft. Eine frühere 2-GB-Vorlage war eine Leistungsreserve, keine nachgewiesene technische Mindestanforderung. Sie ist nicht mehr die Standardvorlage und wird nicht bereitgestellt.

## Sprachmodell und Anwendungskern

Für echte Versuche kann das Modell bei einem API-Anbieter wie OpenAI laufen. Der eigene Python-Dienst erstellt den Modellkontext, übermittelt die Anfrage, verarbeitet vorgeschlagene Toolaufrufe über das Gateway und protokolliert sowie bewertet die beobachteten synthetischen Wirkungen. Das Modell führt die Ticketoperationen nicht eigenständig beim Anbieter aus: Der Anwendungskern kontrolliert sie und gibt die Toolergebnisse als Kontext zurück. Dafür ist kein selbst gehostetes LLM und keine eigene GPU erforderlich.

Die eigene Anwendung benötigt weiterhin CPU und Arbeitsspeicher für HTTP-Anfragen, PDFs, Versuchssteuerung, Dateien und Auswertung. API-Nutzung kann zusätzlich beim Modellanbieter kostenpflichtig sein, unabhängig vom kostenlosen Render-Betrieb. Die jetzige Oberfläche startet ausschließlich Mock-Läufe. Echte Modellaufrufe bleiben dem separat freizugebenden Pilot mit Anbieter-Konfiguration, Budgetkontrolle und nachgewiesener äußerer Isolation vorbehalten. Modellschlüssel gehören ausschließlich ins Backend, niemals in GitHub Pages, Browsercode oder den Labor-Zugangscode.

## Prüfung der Hosting-Variante

Die CI baut den tatsächlichen Hosted-Modus unter `/llm-agent-security-lab/` und verbindet ihn im Browser mit einem separaten HTTPS-Testbackend. Die selbstsignierten Testzertifikate und der öffentliche synthetische Testcode gelten ausschließlich für diese wegwerfbare Testumgebung; produktive TLS-Prüfungen werden dadurch nicht abgeschaltet.

Geprüft werden Anmeldung/Abmeldung, Ablehnung ohne Code, fehlende Token-Speicherung, der Speicherhinweis, PDF-Download und -Import samt Bestätigung, Mock-Versuch und authentifizierter Archivdownload. Browserdiagnosen liegen als kurzzeitig aufbewahrtes CI-Artefakt vor. Ein erfolgreicher Test der Testumgebung ersetzt die abschließende Prüfung der tatsächlich veröffentlichten Adresse nicht. Die konkret ausgeführten Prüfungen und Einschränkungen stehen in [validation.md](validation.md).

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
- [Render Free: Ruhezustand, Datenverlust und Kontingente](https://render.com/docs/free)
- [Render-Preise: Workspace und Compute getrennt](https://render.com/pricing)
- [Persistente Disks und Deploymentgrenzen](https://render.com/docs/disks)
- [Render-Blueprint-Spezifikation](https://render.com/docs/blueprint-spec)

Die Bereitstellung ändert die Erreichbarkeit, nicht die experimentellen Varianten B/F/P/FP oder deren Auswertung. Die Hosting-Änderungen und Tests wurden mit Codex unterstützt; fachliche Autorenabnahme und ein geprüfter echter API-Pilot werden dadurch nicht ersetzt.
