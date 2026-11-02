# Online-Werkbank: GitHub Pages und Render

Stand: 2. November 2026. Der bestehende Render-Webservice verwendet den kostenpflichtigen Compute-Plan. Sebastian hat anschließend den GitHub-Login für beide Autoren und eine persistente Disk genehmigt. Die folgende Übersicht unterscheidet den bekannten Betrieb von implementierten und noch nicht aktivierten Änderungen.

| Geprüfter Bestandteil | Beobachtung am 2. November 2026 |
|---|---|
| Oberfläche | [GitHub Pages](https://sxba-04.github.io/llm-agent-security-lab/), getrennt vom Python-Dienst |
| Render-Service | `srv-dbhmac67bikc73f0cvug`, Frankfurt, eine Instanz |
| Compute | `0.5c-512mb` (früher Starter): 0,5 CPU, 512 MB RAM; Upgrade vom Betreiber bestätigt und im Servicezustand geprüft |
| Deployment | Laufenden Commit im Render-Deployment und im zugehörigen CI-Lauf prüfen; frühere Prüfprotokolle sind keine fortlaufende Statusanzeige. |
| Betriebseinstellungen | Branch `main`, Auto-Deploy `checksPass`, Health Check `/healthz`, PR-Vorschauen aus |
| Speicherung | Startprotokoll meldet weiterhin flüchtigen Speicher; keine Disk in Serviceantwort oder Ereignishistorie nachgewiesen, keine Postgres-/Key-Value-Instanz vorhanden |
| Zugangscode | Sebastian bestätigte seine erfolgreiche Anmeldung; der vorhandene Code war lediglich falsch eingegeben worden. Keine Rotation durchgeführt. |
| GitHub-Login | Optional implementiert und lokal geprüft; OAuth-App, Backend-Konfiguration und echter Login noch ausstehend. |
| Disk-Freigabe | 1 GB genehmigt, Speicherkosten bis höchstens 1 USD/Monat. Einrichtung und Persistenzprüfung noch ausstehend. |

Die bisherige Prüfung der Render-Verwaltung und Logs war lesend. Sie bestätigt weder einen neuen authentifizierten Kampagnenlauf noch eine getestete Dauerhaftigkeit gespeicherter Belege. Die frühere Live-Prüfung vom 29. Oktober umfasste PDF-Download/-Import, acht Mock-Läufe und Archivprüfung; ihr temporärer Zugangscode wurde danach absichtlich entfernt. Die [Validierungsdokumentation](validation.md) hält diese historischen Tests fest.

## Was das Upgrade ändert

Der kostenpflichtige Compute-Plan bietet 0,5 statt 0,1 CPU; der Arbeitsspeicher bleibt bei 512 MB. Der Free-Ruhezustand nach Inaktivität entfällt. Das Upgrade richtet **keine persistente Disk und keine Datenbank** ein. Ohne eine solche Einrichtung gehen Dateien weiterhin bei Neustart oder Deployment verloren. Für diesen Wechsel ist kein Umbau des Versuchskerns nötig.

FastAPI ist das Python-Webframework der Anwendung. **FastAPI Cloud** ist ein eigenständiger Hostinganbieter; die Nutzung von FastAPI verpflichtet nicht zu dessen Verwendung. Der bestehende Backend-Dienst läuft weiter auf Render. Eine zweite Bereitstellung bei FastAPI Cloud würde eine eigene Betriebs- und Migrationsentscheidung benötigen.

## Aufbau und Funktionsumfang

GitHub Pages liefert die gebaute React-Oberfläche unter `https://sxba-04.github.io/llm-agent-security-lab/`. Die Oberfläche spricht nach Anmeldung mit dem Python-Dienst unter `https://llm-agent-security-lab-demo-api.onrender.com` über HTTPS. Dort laufen derselbe Versuchskern, die PDF-Extraktion, die Archivierung und die Bewertung wie in der lokalen Werkbank. Es wird keine zweite Versuchsauswertung in JavaScript implementiert.

GitHub Pages führt selbst keinen Python-Server aus. Für die Nutzung ohne lokalen Prozess braucht es deshalb **zusätzlich den laufenden Backend-Dienst**. Die bestehende Testumgebung verwendet weiterhin einen flüchtigen Workspace: **Hochgeladene PDFs, Versuche und Bewertungen gehen bei Neustart oder Deployment verloren.** Benötigte Archive vorher herunterladen und wichtige Studienbelege außerhalb dieser Umgebung sichern. Die Oberfläche bleibt im Mock-Modus; diese Veröffentlichung aktiviert weder echte Modellaufrufe noch ein API-Budget.

| Bestandteil | Betrieb und Zugriff |
|---|---|
| GitHub Pages | Öffentlich erreichbare Anmeldeseite und statische Frontend-Dateien. Enthält keine Zugangscodes, Workspace-Dateien oder privaten Bewertungen. |
| Python-Backend | Datenzugriff und Änderungen erst mit gültigem Zugangscode oder, nach Aktivierung, eigener GitHub-Laborsitzung. Öffentlich sind nur `/healthz`, die Anmeldearten unter `/api/auth/config` und die begrenzten GitHub-Anmeldeendpunkte. |
| Flüchtiger Test-Workspace | Gemeinsame Kampagnen, PDF-Originale, bestätigte Extraktionen, Bewertungen und Provenienz für beide Autoren, nur bis zum Zurücksetzen des Dienstes. Keine dauerhafte Belegablage. |
| Lokale Werkbank | Bleibt mit dem bisherigen Startbefehl und eigenen lokalen Daten nutzbar. Lokale und gehostete Daten werden nicht automatisch synchronisiert. |

## 1. Backend bereitstellen

`render.yaml` beschreibt einen einzelnen Python-Webservice `llm-agent-security-lab-demo-api` in Frankfurt mit `plan: 0.5c-512mb`, ohne Disk, Datenbank oder zusätzlichen Worker. Der Workspace liegt unter `/tmp/security-lab-demo`; `LAB_STORAGE_MODE=ephemeral` aktiviert den Speicherhinweis. Der bestehende Dienst wurde direkt über die Render-Verwaltung eingerichtet; seine dortige Konfiguration ist die Quelle der tatsächlichen Einstellungen. Änderungen an `render.yaml` werden dadurch nicht automatisch als Infrastrukturänderungen übernommen. Eine spätere Blueprint-Verwaltung muss bewusst eingerichtet werden; keinen zweiten Dienst für dieselbe Werkbank anlegen.

**Bestehenden Dienst weiterverwenden:** Compute-Plan und die anschließend genehmigte 1-GB-Disk sind durch Betreiberentscheidungen gedeckt; für Speicher gilt die Obergrenze von 1 USD/Monat. Andere Dienste, größere Compute-Pläne oder Datenbanken sind davon nicht umfasst. Der aktuelle Dienst benötigt keinen Ersatz und keinen zweiten Backend-Host. Bis zur tatsächlichen Speichermigration bleiben die folgenden flüchtigen Laufzeiteinstellungen bestehen.

1. Render mit dem eigenen GitHub-Konto verbinden und diesem Repository Zugriff geben. Nicht nur die öffentliche Repository-URL importieren: diese Alternative unterstützt keine automatischen Deployments.
2. Die oben genannten Einstellungen und die Kosten-/Ressourcenübersicht des bestehenden Dienstes prüfen. Der Branch ist `main`; automatische Updates auf erfolgreiche CI-Prüfungen einstellen. Beim Blueprint entspricht dies `autoDeployTrigger: checksPass`. Zusätzliche Ressourcen erst nach einer entsprechenden Projektentscheidung einrichten.
3. Für jeden Autor einen unabhängigen Zugangscode lokal erzeugen und dessen SHA-256-Hash als `LAB_ACCESS_TOKEN_HASHES` konfigurieren. Ein erster Code genügt zur Einrichtung; weitere Hashes können später kommagetrennt ergänzt werden. Die echten Codes gehören ausschließlich zu den jeweiligen Autoren.
4. `LAB_WORKSPACE=/tmp/security-lab-demo` und `LAB_STORAGE_MODE=ephemeral` setzen. Der Dienst erstellt seine Arbeitsverzeichnisse selbst; es wird keine persistente Disk eingehängt.
5. Nach erfolgreichem Backend-Deployment dessen HTTPS-Adresse übernehmen. `/healthz` muss erreichbar sein; `/api/cases` muss ohne Zugangscode mit HTTP 401 antworten. Die authentifizierte `/api/health`-Antwort muss `storage_mode: ephemeral` und `mode: mock` enthalten. Anschließend die Pages-Verbindung und den Speicherhinweis tatsächlich im Browser prüfen.

Die Vorlage verwendet das unveränderte Python-Lockfile. Der Hosting-Start erfolgt durch `python -m security_lab.hosted_cli`; der übliche lokale Launcher wird nicht für eine öffentliche Freigabe umkonfiguriert. Es bleibt bei einer Instanz und einem Worker. Mehrere Worker oder horizontale Skalierung sind mit den vorhandenen In-Process-Sperren und der dateibasierten Speicherung nicht unterstützt.

Der aktuelle Plan stellt 512 MB RAM bereit. Das Labor lädt keine Modellgewichte; ein gewöhnlicher Mock-Ablauf ist deshalb ein sinnvoller Test für diese kleine Instanz. Das ist noch kein Nachweis, dass beliebig große oder parallele PDF-Importe unter dieser Speichergrenze gelingen. Die tatsächliche Ressourcennutzung nach Bereitstellung prüfen und Fehler offen ausweisen; zusätzliche Ressourcen nicht allein aufgrund des kostenpflichtigen Plans aktivieren.

### Zugangscodes ohne Speicherung im Repository erzeugen

Jeder Autor kann diesen Befehl auf seinem eigenen Rechner ausführen. Er erzeugt einen zufälligen Code mit 256 Bit Entropie und den dazugehörigen Hash:

```powershell
uv run python -c "import hashlib,secrets; code=secrets.token_urlsafe(32); print('Persoenlicher Zugangscode:',code); print('Server-Hash:',hashlib.sha256(code.encode('ascii')).hexdigest())"
```

Den Code unmittelbar in einem Passwortmanager speichern; nur den Server-Hash zur Einrichtung weitergeben. Keine Codes in Git-Dateien, Screenshots, Pull Requests, Chatnachrichten, GitHub-Variablen oder Frontend-Builds eintragen. Der Befehl enthält selbst keinen Zugangscode, aber seine Terminalausgabe ist vertraulich. Keine selbst gewählten kurzen Passwörter verwenden.

Der Browser hält den eingegebenen Code nur im Arbeitsspeicher. Abmelden oder Neuladen erfordert eine erneute Eingabe; es gibt keine Speicherung in `localStorage` oder `sessionStorage`. PDF- und Archivdownloads übertragen die Authentifizierung als Header, niemals als URL-Parameter.

### Verlorener Code und ungültige Sitzung

Der persönliche Code wird durch den obigen Generator erstellt, nicht von GitHub Pages oder Render vergeben. Der Server speichert nur seinen SHA-256-Hash und kann den ursprünglichen Code daraus nicht zurückgewinnen. Der Code schützt auch Downloads und Änderungen; ohne einen solchen Zugriffsschutz wäre der öffentlich erreichbare Dienst für fremde Personen bedienbar.

Ein Backend-Neustart ändert den konfigurierten persönlichen Code nicht. Er erzeugt jedoch ein neues internes Sitzungstoken für schreibende Anfragen. Bei einem als ungültig erkannten Sitzungstoken verwirft der Client nur dieses interne Token und zeigt an, dass die angeforderte Änderung nicht ausgeführt wurde. Die nächste bewusst ausgelöste Aktion lädt zuerst ein neues Sitzungstoken; sie benötigt dafür keine erneute Eingabe des weiterhin gültigen persönlichen Codes. Schreibaktionen werden nicht automatisch wiederholt. Bei Zugangscode-Anmeldung bedeutet eine echte HTTP-401-Antwort, dass der persönliche Code fehlt oder keinem konfigurierten Hash entspricht. Bei GitHub-Anmeldung kann sie eine abgelaufene oder widerrufene Laborsitzung bedeuten; dann erneut mit GitHub anmelden. Netzwerk-, TLS- und CORS-Fehler können ebenfalls die Anmeldung verhindern und sind nicht automatisch ein falscher Code.

Bei verlorenem Code:

1. Einen neuen Code lokal erzeugen und im Passwortmanager sichern.
2. Die vorhandenen `LAB_ACCESS_TOKEN_HASHES` im Render-Dienst prüfen. Den Hash von Jonahs weiterhin gültigem Zugang erhalten. Nur den eindeutig zugeordneten verlorenen oder kompromittierten Hash ersetzen; bei unklarer Zuordnung beide Zugänge gemeinsam erneuern.
3. Nur die Hashliste in der Backend-Konfiguration aktualisieren und den Deploymentabschluss abwarten. Vor dem dadurch ausgelösten Neustart wichtige Belege exportieren.
4. Mit dem neuen Code anmelden und geschützte Lese-/Schreibfunktionen prüfen. Wenn der alte Code noch verfügbar ist, seine Ablehnung kontrollieren.

Ein Frontend-Neubau ist für diese Rotation nicht nötig. Niemals zur Wiederherstellung den Zugriffsschutz ausschalten oder einen Klartextcode in GitHub Actions beziehungsweise Pages eintragen.

### GitHub-Login und Sitzungsverwaltung

Der optionale [GitHub-Login](github-login.md) ist implementiert. Der Server lässt ausschließlich konfigurierte, unveränderliche GitHub-Konto-IDs zu. Beide Autoren erhalten dieselben Rechte zum Lesen und Bearbeiten des gemeinsamen Workspace und können nur ihre eigenen GitHub-Sitzungen verwalten. Öffentliche Registrierung und eine eigene Passwortverwaltung gibt es nicht.

Die Anmeldung verwendet eine feste Pages-Rückleitung, State und PKCE. Der GitHub-Token bleibt beim Backend und wird nach der Identitätsprüfung verworfen; der Browser erhält einen eigenen zufälligen Labortoken. Er bleibt im Arbeitsspeicher. Nur der kurzlebige PKCE-Verifier mit State wird für die Rückleitung vorübergehend in `sessionStorage` gehalten und beim Callback entfernt. Sitzungen laufen spätestens nach acht Stunden ab; Neustarts widerrufen sie. Pro Konto bleiben höchstens acht aktiv, danach wird die älteste eigene Sitzung ersetzt. Der vorhandene Zugangscode bleibt ein unabhängiger Rückfallweg.

**Noch nicht live aktiviert:** Die OAuth-App-Registrierung wurde vorbereitet, aber die automatische Freigabeprüfung hat das Absenden bis zu einer konkreten Aktionsbestätigung abgelehnt. Es wurde keine OAuth-App und kein Client-Secret erstellt. Die vier Backend-Einstellungen und ein tatsächlicher GitHub-Anmeldetest stehen aus. Fehlende oder teilweise gesetzte Konfiguration darf nicht durch Abschwächen der Zugriffskontrollen umgangen werden.

GitHub bestätigt die verwendete Konto-ID. Das ordnet bestehende wissenschaftliche Bewertungen nicht automatisch einer Person zu und erzwingt keine unabhängigen A/B-Bewertungen. Die fachlichen Bewertungsregeln bleiben unverändert. Ebenso bleibt die experimentelle Autorisierung P vom Betreiberlogin getrennt.

### Backend-Einstellungen

| Variable | Wert / Bedeutung |
|---|---|
| `LAB_PUBLIC_ORIGIN` | Eigene HTTPS-Origin ohne Pfad. Auf Render kann sie entfallen; dann wird `RENDER_EXTERNAL_URL` verwendet. Bei eigener Domain explizit setzen. |
| `LAB_FRONTEND_ORIGIN` | `https://sxba-04.github.io` – ohne Repository-Pfad und ohne abschließenden Slash. |
| `LAB_ACCESS_TOKEN_HASHES` | Kommagetrennte SHA-256-Hashes der zufälligen Zugangscodes, im Backend-Secret-Speicher konfigurieren. |
| `LAB_WORKSPACE` | `/tmp/security-lab-demo` für die bestehende flüchtige Testumgebung. Absoluter Pfad, keine dauerhafte Speicherung. |
| `LAB_STORAGE_MODE` | `ephemeral` für die bestehende Testumgebung; nur `ephemeral` und `persistent` sind gültig. Ohne Angabe gilt `persistent`. Die Einstellung beschreibt den vorgesehenen Speicherlebenszyklus; sie richtet selbst keine Disk ein und löscht keine Dateien. |
| `LAB_GITHUB_CLIENT_ID`, `LAB_GITHUB_CLIENT_SECRET` | Optionale OAuth-App-Konfiguration ausschließlich im Backend; derzeit noch nicht gesetzt. Secret niemals veröffentlichen. |
| `LAB_GITHUB_REDIRECT_URI` | Feste Rückleitung zur Pages-Anwendung; Einrichtung siehe [GitHub-Login](github-login.md). |
| `LAB_GITHUB_ALLOWED_USER_IDS` | Kommagetrennte, zuvor eindeutig geprüfte numerische GitHub-Konto-IDs der beiden Autoren. |
| `PORT` | Vom Hostinganbieter bereitgestellter HTTP-Port hinter dessen HTTPS-Proxy. |

Die Origin-/Hostprüfung bleibt aktiv. CORS erlaubt nur die exakt konfigurierte Frontend- beziehungsweise Backend-Origin; die GitHub-Anmeldung verlangt ausschließlich die Frontend-Origin. Auch Fehlermeldungen und Preflight-Anfragen müssen diesen Vertrag erfüllen. Die Browser-Anmeldung verwendet keine Drittanbieter-Cookies. Der Hoster beendet TLS vor dem Python-Dienst; die öffentliche HTTPS-Origin wird explizit validiert, statt beliebigen weitergeleiteten Headern zu vertrauen.

## 2. GitHub Pages mit dem Backend verbinden

1. Im Repository unter **Settings → Secrets and variables → Actions → Variables** die Repository-Variable `LAB_API_BASE_URL` auf die öffentliche Backend-Origin setzen. Der bestehende Wert ist `https://llm-agent-security-lab-demo-api.onrender.com`. **Keinen Zugangscode hinzufügen.** Die URL darf keinen API-Pfad, Benutzerinformationen, Query oder Fragment enthalten.
2. Unter **Settings → Pages → Build and deployment → Source** **GitHub Actions** auswählen. HTTPS aktiviert lassen.
3. Unter **Actions → Hosted workbench and Pages → Run workflow** den Branch `main` starten.
4. Den erfolgreichen Build und das `github-pages`-Deployment prüfen; anschließend die veröffentlichte URL öffnen und mit dem eigenen Code anmelden.

Ohne `LAB_API_BASE_URL` prüft der Workflow weiterhin den Hosted-Build und die Browserintegration, veröffentlicht aber bewusst keine funktionslose Website. Der Jobbericht nennt die fehlende Einrichtung. Ein beliebiger Platzhalter darf daher nicht als Produktionswert eingetragen werden. Die Repository-Variable ist öffentliches Konfigurationswissen, kein Geheimnis.

Nur `frontend/dist` wird zu Pages übertragen. Der Workflow veröffentlicht weder Python-Quellverzeichnisse noch den Workspace. Pull Requests führen die Prüfungen aus, veröffentlichen aber nichts. Das Deployment hat auf `main` begrenzte Pages-/OIDC-Rechte; Test- und Buildjobs besitzen nur Lesezugriff auf Repository-Inhalte. Die verwendeten GitHub Actions sind auf konkrete Commit-SHAs festgelegt.

## 3. Automatische Updates und Betrieb

Neue Änderungen auf `main` lösen den Frontend-Workflow aus. GitHub Pages veröffentlicht nach dem erfolgreichen Build und den HTTPS-Integrationstests dieses eigenen Workflows. Das über GitHub angebundene Backend verwendet **After CI Checks Pass**: Render wartet auf alle erkannten Prüfungen des Commits, auch externe Checks wie SonarQube. GitHub-Schlusszustände `success`, `neutral` und `skipped` gelten dabei als bestanden; ein fehlgeschlagener Check verhindert das automatische Backend-Deployment. Ein grüner Pages-Build allein belegt deshalb noch kein aktualisiertes Backend. Neue Qualitätsprüfungen zuerst tatsächlich ausführen und fehlgeschlagene Befunde beheben, statt den Deployment-Schutz auszuschalten.

Beide Dienste veröffentlichen getrennt; sie wechseln nicht atomar im selben Moment. API-Änderungen müssen deshalb während der Übergangsphase mit der jeweils anderen Version kompatibel bleiben. Nach Änderungen an CI oder API den veröffentlichten Pages-Stand und das Render-Deployment desselben `main`-Commits kontrollieren. Die obige Bestandsprüfung hält einen Zeitpunkt fest und aktualisiert sich nicht automatisch.

Der aktuelle kostenpflichtige Dienst verwendet keinen Free-Ruhezustand. Ein zusätzlicher Keep-alive-Dienst ist nicht erforderlich. Nach Deployments trotzdem Health Check, Authentifizierung und den tatsächlich laufenden Commit prüfen.

Bei Neustart oder Deployment gehen die Dateien des flüchtigen Workspace verloren. Das betrifft auch bestätigte PDF-Texte, Bewertungen und mögliche Unterbrechungsnachweise. Vor geplanten Updates Versuche beenden und benötigte Archive herunterladen. Die Oberfläche zeigt auf allen Arbeitsseiten einen Hinweis. Ein laufender Mock-Versuch kann abgebrochen werden und wird nicht automatisch wiederholt. Falls die Belege gelöscht wurden, kann daraus kein vollständiger Lauf rekonstruiert oder als Erfolg ausgegeben werden. Nach einem Backend-Neustart kann eine bereits geöffnete Seite noch das alte Sitzungstoken besitzen. Den entsprechenden Hinweis beachten und die gewünschte Aktion bewusst erneut auslösen; es gibt keine automatische Wiederholung von Änderungen. Ein Neuladen der Seite beendet dagegen die nur im Arbeitsspeicher gehaltene Anmeldung und erfordert eine erneute Anmeldung. Für GitHub-Sitzungen ist sie zusätzlich nach einem Serverneustart nötig; der persönliche Zugangscode selbst wird durch den Neustart nicht geändert.

Zugangscodes und freigegebene GitHub-Konten erlauben denselben gemeinsamen Arbeitsbereich. Beide Autoren können Kampagnen und Bewertungsansichten öffnen; GitHub-Sitzungsverwaltung trennt nur den Zugriff auf eigene Sitzungen. Die bestehende Trennung in Bewertung A/B unterstützt den Arbeitsablauf, garantiert aber keine technische Geheimhaltung gegenüber dem jeweils anderen Autor. Für unabhängige Urteile die getrennten Bewertungsansichten und organisatorischen Regeln weiter einhalten.

Nur synthetische Versuchsdaten verwenden. Benötigte vollständige Kampagnenarchive rechtzeitig exportieren und die Wiederherstellung lokal prüfen. Separat hochgeladene Quellen ohne Kampagnenzuordnung müssen zusätzlich außerhalb der Umgebung vorhanden sein. Der flüchtige Dienst darf nicht die einzige Ablage wichtiger Studienbelege sein. Beim Wechsel des Hostinganbieters PDF-Originale, Bewertungen und Provenienz gemeinsam mit den Laufdaten übernehmen.

### Genehmigte, noch ausstehende Änderung: dauerhafte Speicherung

Die Anwendung unterstützt einen frei konfigurierten Workspace und den Modus `persistent` bereits. Für den derzeitigen Einprozessbetrieb ist eine Render-Disk eine passende, kleine Erweiterung; eine Datenbankmigration ist dafür nicht erforderlich. Die zusätzliche Disk ist ein separat berechnetes Produkt. Sebastian hat 1 GB und bei Bedarf Speicher bis höchstens 1 USD/Monat genehmigt. Sie wurde noch nicht eingerichtet; der Browserzugriff auf die erforderliche Render-Verwaltung ist noch nicht angemeldet. `LAB_WORKSPACE` und `LAB_STORAGE_MODE` bleiben deshalb unverändert.

Der konkrete Umstieg besteht aus folgenden Schritten:

1. Benötigte Kampagnen inklusive Quellen, Bewertungen und Provenienz exportieren, Archive prüfen und eine lokale Wiederherstellung testen. Separat hochgeladene, noch nicht verwendete Quellen zusätzlich sichern.
2. Mit 1 GB beginnen, den angezeigten Preis gegen die genehmigte monatliche Obergrenze prüfen und den Mountpfad festlegen; eine neue Disk kann später vergrößert, aber nicht verkleinert werden. Nur der Mountpfad ist persistent.
3. Die genehmigte Disk am bestehenden Dienst beispielsweise unter `/var/data` anlegen. Dieser Vorgang löst ein Deployment aus; die alten `/tmp`-Dateien werden dadurch nicht automatisch übernommen.
4. `LAB_WORKSPACE=/var/data/security-lab` und erst zusammen mit der tatsächlichen Disk `LAB_STORAGE_MODE=persistent` setzen. Bei einer bereits befüllten Umgebung die gesicherten Archive kontrolliert wiederherstellen.
5. Einen synthetischen Testbeleg anlegen, einen kontrollierten Neustart durchführen und den unveränderten Beleg anschließend prüfen. Erst dann die Persistenz als verifiziert dokumentieren.

Die bloße Umschaltung der Variablen macht den Speicher nicht dauerhaft. Eine Disk erlaubt nur eine Instanz und bringt kurze Unterbrechungen bei Deployments mit sich; dies passt zur bestehenden Architektur, muss aber in der Versuchsplanung berücksichtigt werden. Render-Snapshots ersetzen keine externen, geprüften Kampagnenarchive. Eine spätere Mehrbenutzer- oder Mehrinstanzarchitektur würde zusätzlich gemeinsame Sperren, Jobs und Datenhaltung benötigen.

## Sprachmodell und Anwendungskern

Für echte Versuche kann das Modell bei einem API-Anbieter wie OpenAI laufen. Der eigene Python-Dienst erstellt den Modellkontext, übermittelt die Anfrage, verarbeitet vorgeschlagene Toolaufrufe über das Gateway und protokolliert sowie bewertet die beobachteten synthetischen Wirkungen. Das Modell führt die Ticketoperationen nicht eigenständig beim Anbieter aus: Der Anwendungskern kontrolliert sie und gibt die Toolergebnisse als Kontext zurück. Dafür ist kein selbst gehostetes LLM und keine eigene GPU erforderlich.

Die eigene Anwendung benötigt weiterhin CPU und Arbeitsspeicher für HTTP-Anfragen, PDFs, Versuchssteuerung, Dateien und Auswertung. API-Nutzung kann zusätzlich beim Modellanbieter kostenpflichtig sein, unabhängig von den Render-Hostingkosten. Die jetzige Oberfläche startet ausschließlich Mock-Läufe. Echte Modellaufrufe bleiben dem separat freizugebenden Pilot mit Anbieter-Konfiguration, Budgetkontrolle und nachgewiesener äußerer Isolation vorbehalten. Modellschlüssel gehören ausschließlich ins Backend, niemals in GitHub Pages, Browsercode oder den Labor-Zugangscode.

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
- [Render-Deployments und erfolgreiche CI-Prüfungen](https://render.com/docs/deploys)
- [Render Compute: CPU und RAM je Plan](https://render.com/docs/compute-plans)
- [Render Free: früherer Ruhezustand und Kontingente](https://render.com/docs/free)
- [Render-Preise: Workspace und Compute getrennt](https://render.com/pricing)
- [Persistente Disks und Deploymentgrenzen](https://render.com/docs/disks)
- [Render-Blueprint-Spezifikation](https://render.com/docs/blueprint-spec)

Die Bereitstellung ändert die Erreichbarkeit, nicht die experimentellen Varianten B/F/P/FP oder deren Auswertung. Die Hosting-Änderungen und Tests wurden mit Codex unterstützt; fachliche Autorenabnahme und ein geprüfter echter API-Pilot werden dadurch nicht ersetzt.
