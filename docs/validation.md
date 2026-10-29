# Technischer Prüfstand

Diese Prüfungen betreffen die Implementierung. Sie sind keine empirischen Ergebnisse über die Angreifbarkeit eines Sprachmodells.

## Actions und Abnahmeanleitung vom 29. Oktober 2026

Sebastian hat zurückgemeldet, dass der aktuelle `main`-Stand nach Synchronisation der Abhängigkeiten und erneutem Frontend-Build auf seinem LUBW-Windows-Laptop funktioniert. Das ist eine bestätigte Einrichtung, keine bereits erledigte gemeinsame fachliche Abnahme.

- Der korrigierte PR-#5-Stand `f3d5d79` besteht alle vier [Windows-/Linux-CI-Jobs](https://github.com/sxba-04/llm-agent-security-lab/actions/runs/40878109252). Die Git-Ausnahme für gemeinsame VS-Code-Tasks wurde mit tatsächlichen Git-Abfragen geprüft; persönliche IDE-Dateien bleiben auch in Unterordnern ignoriert.
- Der neue Actions-Helfer wurde lokal unter Linux mit Python 3.12.14 geprüft: Testsuite mit 257 Tests, `OK (skipped=1)`; der echte Windows-Lesehandle-Test bleibt auf Linux übersprungen. Drei neue Tests prüfen ungültige Workflow-Eingaben, unveränderte vorhandene Belege und Fehlerweitergabe ohne falschen Erfolgsstatus.
- Tatsächliche Helferläufe mit 24 und 288 Mock-Läufen durchliefen Auswertung, Export unbewerteter Review-Unterlagen, CSV, Archivprüfung, Wiederherstellung und identische Neuauswertung. Ein zusätzlich reproduzierter Auswertungsfehler nach 24 Läufen begründete die getrennten, ausdrücklich ungeprüften Diagnoseartefakte für Fehlerfälle.
- Die [Klickanleitung](manual-acceptance.md) wurde anhand der React-Beschriftungen und unabhängig ausgeführter Mock-Läufe geprüft. Ein tatsächlicher FastAPI-TestClient-Durchlauf importierte und bestätigte sechs Beispiel-PDFs, führte die 24-Lauf-Kampagne aus und prüfte Quellenhashes, Vergleichswerte und Archiv-Rundlauf. Eine weitere unabhängige Gegenprüfung bestätigte die Solltabellen, 24 Vergleichsgruppen und Bewertungs-/Archivschritte. Ein vollständiger menschlicher Browser-Abnahmedurchlauf wird dadurch nicht behauptet.
- Das [Ruleset für `main`](branch-protection.md) wurde tatsächlich aktiviert; GitHub bestätigt `protected: true`, aktive Regeln, die vier CI-Checks mit GitHub-Actions-Herkunft und keine Bypass-Berechtigung.

Die neuen Workflow-Ausführungen unter GitHub und ihre Reviews werden am endgültigen Folge-PR dokumentiert. Die [Protokollvorlage](manual-acceptance-record-template.md) bleibt ausdrücklich unausgefüllt: Autorenentscheidungen, menschliche Bewertungen und Jonahs Einrichtung sind weiterhin offen. Es wurden keine echten Modellaufrufe ausgeführt.

## Gemeinsame VS-Code-Aufgaben vom 29. Oktober 2026

Auf Basis von `main` bei `421dfa4` wurden die gemeinsamen Tasks und korrigierten Windows-Befehle lokal unter Windows mit Python 3.12.15, uv 0.13.5 und Node.js 24.22.1/npm 11.19.1 geprüft. Die PowerShell-Ausführungsrichtlinie blieb `Restricted`; die Tasks verwenden unter Windows `npm.cmd` statt `npm.ps1`.

- Alle 13 Taskdefinitionen wurden als Shell-Befehle einschließlich ihrer Abhängigkeiten mit der persönlichen Workspace-Umgebung ausgeführt. Paketinstallation aus beiden Lockdateien, TypeScript-Prüfung und Produktionsbuild waren erfolgreich.
- 254 Python-Tests und 22 React-Tests bestanden. Beide echten Playwright-/FastAPI-Browsertests bestanden, einschließlich PDF-Verarbeitung und mobiler Navigation. Die Browser liefen im eigenen Testarbeitsverzeichnis.
- Eine frische Kopie der versionierbaren Dateien in einem Pfad mit Leerzeichen enthielt nur die gemeinsame `tasks.json`, keine persönlichen IDE-Einstellungen oder vorherige Projektumgebung. Mit extern bereitgestelltem Werkzeug-PATH und Netzwerkzugang bestanden Gesamtinstallation, Build, 24 Demo- und 96 Entwicklungsläufe.
- Anwendung und Playwright-Berichtsserver antworteten nach dem Start jeweils mit HTTP 200. Alle 616 vorab erfassten vorhandenen Belegdateien außerhalb des Browser-Testarbeitsverzeichnisses blieben unverändert.
- Die Git-Ausnahmen und die Vererbung persönlicher Terminal-Umgebungsvariablen wurden unabhängig am installierten VS-Code-Code geprüft. Das VS-Code-Auswahlmenü selbst wurde nicht automatisiert bedient. Ein Hinweis zu Linux-Systembibliotheken wurde nach der Gegenprüfung ergänzt; diese Runde behauptet keine lokale Ausführung unter Linux/macOS oder auf Jonahs Rechner.

Die Änderung betrifft Entwicklungskomfort und Dokumentation. Versuchskern, Fallkatalog, Schutzvarianten, Auswertung und Laufgrenzen bleiben unverändert. Es wurden keine echten Modellanfragen ausgeführt. Der GitHub-CI- und Reviewstatus ist am zugehörigen PR-Head gesondert zu prüfen.

## Ergänzung vom 27. Oktober 2026

PR #3 wurde auf Commit `186ca6d` mit erfolgreichen Codex-Code- und Security-Reviews sowie bestandener GitHub-CI geprüft und als `9a0dfebc` gemergt. Copilot konnte wegen seines Kontingents erneut nicht prüfen; die ausdrücklich genehmigte Ausnahme ist im PR dokumentiert.

Die anschließende [Repository-Prüfung](repository-audit-2026-10-27.md) und ihre bestätigten Fehlerkorrekturen wurden lokal unter Linux mit Python 3.12.14 und Node.js 24.19.0 geprüft:

- 254 Python-Tests erfolgreich; genau ein Test mit echtem Windows-Lesehandle wurde auf Linux übersprungen. Die portable Windows-Fehler-Injektion lief mit.
- 22 React-Verhaltenstests, TypeScript-Prüfung und Produktionsbuild erfolgreich. Der Frontend-Lockfile wurde mit einem sauberen `npm ci` installiert; Node 24 ab 24.15.0 ist jetzt ausdrücklich erforderlich.
- 96 tatsächliche Mock-Einzelläufe über alle zwölf Entwicklungsfälle, zwei Quellen und vier Varianten ergeben 24 Vergleichsgruppen mit je vier gemeinsamen gültigen Blöcken und keinen Ausschlüssen. Alle bleiben `engineering_only`.
- Fehler bei Schreiben, Synchronisieren und atomarer Veröffentlichung neuer Bewertungen/PDF-Bestätigungen sowie konkurrierende Zieldateien werden gezielt geprüft. Gesunde PDF- und Bewertungssätze bleiben neben beschädigten Einträgen erreichbar.
- Echte Archiv-Rundläufe prüfen Bewertungen nach Wiederherstellung in einen frischen Workspace sowie neben dem Original. Alle archivierten Review-Dateien bleiben unverändert; fremde Zuordnungen und nachträglich veränderte Laufhashes werden abgewiesen.
- Unabhängige Quellcode-Gegenprüfungen betrafen Speichergrenzen, PDF-Textbestätigung, Wiederherstellung, Browsernavigation und CI. Ein zusätzlicher tatsächlicher React-Modultest reproduzierte zunächst einen Fehler bei mehrstufiger Browserhistorie und bestand nach der Korrektur.

Der erneute lokale Chromium-Download scheiterte an ungültigen ZIP-Daten vom Playwright-CDN; deshalb wird auch für diese Runde kein lokal bestandener Browsertest behauptet. Die zwei E2E-Testdefinitionen ließen sich erfolgreich laden. Die CI ist um echte Chromium-/FastAPI-Browserprüfungen auf Windows und Linux erweitert. Ihr tatsächlicher Ergebnisnachweis steht am endgültigen Folge-PR-Commit; die Workflow-Konfiguration allein behauptet keinen Erfolg. Der frühere Prüfstand folgt unten unverändert als historische Einordnung.

## Bestätigte Einrichtung beim Team

Sebastian hat die erfolgreiche Einrichtung des ursprünglichen Projektgerüsts auf seinem LUBW-Windows-Laptop in VS Code zurückgemeldet. Am 23. Oktober wurde auch die neue Weboberfläche durch den lokalen Codex technisch geprüft; die Ergebnisse stehen im folgenden Windows-Prüfstand. Die fachliche Abnahme durch die Autoren, Jonahs Rechner und Sebastians private Rechner bleiben gesondert zu prüfen.

## Zusätzlicher lokaler Windows-Prüfstand

- Python 3.12.15, uv 0.13.5 und Node.js 24.22.1 mit npm 11.19.1; Paket- und Browserdownloads über den Firmenproxy mit aktiver TLS-Prüfung. Das vorhandene Node.js 24.13.1 lag unter der Mindestversion einiger festgelegter Testabhängigkeiten.
- Der erste echte Browsertest reproduzierte einen Abbruch beim gleichzeitigen Lesen und atomaren Ersetzen von `manifest.json` unter Windows (`WinError 5`). Die Korrektur wiederholt ausschließlich den Austausch der bereits synchronisierten Tempdatei bei Windows-Fehlern 5, 32 oder 33 für höchstens etwa eine Sekunde. Modell- und Toolarbeit wird nicht wiederholt; dauerhafte und andere Fehler bleiben Fehler.
- Danach bestanden alle 230 Python-Tests einschließlich fünf neuer Regressionstests und eines echten Windows-Lesehandles. Zusätzlich bestanden zwölf React-Tests, TypeScript-Prüfung, Produktionsbuild und beide echten Playwright-Browsertests mit FastAPI, PDF-Import und mobiler Navigation.
- Drei weitere Mock-Kampagnen mit jeweils 24 Läufen und häufigen parallelen Fortschrittsabfragen wurden vollständig abgeschlossen. Eine unabhängige technische Gegenprüfung des Fixes fand keine weiteren Befunde. Menschliches Review und wissenschaftliche Bewertung werden damit nicht behauptet.

## Ursprünglich unter Linux ausgeführte Prüfungen

- Python 3.12.14 unter Linux; `uv sync --locked --extra web --group dev` erfolgreich.
- 225 Python-Tests erfolgreich, einschließlich FastAPI-TestClient und tatsächlicher PDF-Extraktion im Unterprozess.
- Zwölf React-Verhaltenstests erfolgreich: kein Start beim Laden/Neuladen, expliziter Start mit Sitzungstoken, getrennte Bewertungsplätze ohne voreingestellte Urteile, Bestätigung des konkreten PDF-Texthashes, inerte Darstellung von Angriffstexten, eingefrorene Bewertungen, Isolation beschädigter Kampagnen und Aktualisierung des Vergleichs bis zum Serienabschluss.
- TypeScript-Prüfung und Vite-Produktionsbuild erfolgreich (Node.js 24).
- Alle zwölf überarbeiteten Entwicklungspaare strukturell validiert; alle 24 Beispiel-PDFs behalten ihre relevanten Textinhalte.
- Vollständiger Entwicklungskatalog: zwölf Paare, vier Varianten, zwei Quellfassungen und drei Wiederholungen ergeben 288 von 288 abgeschlossene Mock-Läufe.
- Kampagne exportiert, alle 579 Dateien verifiziert, wiederhergestellt und Zusammenfassung samt CSV aus den wiederhergestellten Originalen neu berechnet. Archivbericht: Integrität geprüft, Belegdateien vollständig; keine Signatur oder Urheberschaftsprüfung.
- Export, zwei synthetische Testbewertungen, Zusammenführung und begründete Klärung im Integrationstest geprüft. Es wurden keine menschlichen wissenschaftlichen Bewertungen erfunden.

## Gegenprüfungen und CI vor der lokalen Windows-Einrichtung

Unabhängige technische Gegenprüfungen betrafen Adapter-/Antwortfehler, Provenienz, Paarbarkeit, Archive sowie die lokalen HTTP- und PDF-Grenzen. Bestätigte Befunde wurden mit Regressionstests korrigiert. Der anschließende GitHub-Review ergab zusätzliche Korrekturen an einmaliger Zusammenführung, gemeinsamer Adjudikation, laufenden CLI-Serien, Wiederherstellungsbelegen und beschädigten beziehungsweise verwaisten UI-Kampagnen. Zusätzliche Korrekturen prüfen sämtliche archivierten Bewertungsstände samt Original-CSV und Vorgängern, halten die Vergleichsansicht aktuell und vermeiden wiederholtes Einlesen unveränderter Kampagnen beim Polling. Die Artikelfakten wurden auf eigenständigen Informationsgehalt präzisiert; anschließend wurden erneut 288 Mock-Läufe und der vollständige Archivablauf geprüft. Ein echter Unterprozess-Test prüft dabei einen lebenden fremden Worker und die Wiederherstellung nach dessen erzwungenem Ende. Insbesondere dürfen abweichende Ausgangsdaten nicht gepaart, fremde Review-Pakete nicht einer Kampagne zugeordnet und fehlende Ereignisduplikate nicht als vollständig ausgegeben werden. Sicherheits- und Proxyprüfungen schließen fremde Hosts/Origins, fehlende Token, Pfadwechsel und parallele Serienstarts ein.

Der lokale Browserdownload war in dieser Arbeitsumgebung nicht erreichbar. Beide echten Chromium-Browsertests bestanden anschließend auf GitHub und erneut zusammen mit 206 Python-Tests unter Windows/Linux und elf React-Tests am Commit `efc6abb`: [CI-Durchlauf](https://github.com/sxba-04/llm-agent-security-lab/actions/runs/39927902245). Geprüft wurden expliziter Start, acht Läufe, Neuladen ohne Doppelstart, Ereignis-/Ticketansicht, Vergleiche, PDF-Download/Import/Bestätigung, getrennte Bewertungsentwürfe und mobile Navigation. Die Desktop- und Mobile-Screenshots wurden visuell geprüft. Deshalb wird kein lokal bestandener Chromium-Test behauptet. GitHub Actions führt die Python-Prüfungen unter Windows und Linux sowie React-Tests, Build und einen echten Browserdurchlauf mit FastAPI aus. Der jeweilige Status ist am aktuellen PR-Commit zu prüfen; vorbereitete CI allein ist kein Erfolgsnachweis. Browserberichte und Screenshots werden als CI-Artefakte gespeichert.

## PDF-Rendering-Korrektur vom 29.10.2026

Ausgangsstand: `f64b2a05a79fc2169751eb934460294fc5b68bd4`. Der vorhandene Generator bettete einen Inhaltsstream direkt in das Seitendictionary ein. pypdf konnte Text daraus lesen; Poppler meldete dagegen einen ungültigen Seitentyp und zeigte keinen Inhalt. Die Korrektur registriert Inhalt und Schrift als indirekte PDF-Objekte.

- Unter Linux mit Python 3.12.14 und gesperrtem pypdf 6.21.2: 259 Python-Tests ausgeführt, erfolgreich mit einer betriebssystembedingten Windows-Auslassung.
- Alle 24 Beispiel-PDFs unabhängig mit Poppler gerendert: keine Rendererfehler, jede Seite mit sichtbarem Inhalt. Eine Beispielseite zusätzlich visuell geprüft.
- Mehrseitige Texte, Umlaute, Klammern und Backslashes sowie HTTP-Download, PDF-Import, Bestätigung und Archiv-Rundlauf geprüft.
- Die neuen Struktur-/Renderingprüfungen gegen den ursprünglichen Generator erzeugten erwartungsgemäß 48 Subtest-Fehler; damit erkennen sie den gemeldeten Defekt tatsächlich.
- Eine unabhängige technische Gegenprüfung wiederholte die PDF-Tests. GitHub-CI und angeforderte Reviews sind gesondert am jeweiligen PR-Head zu prüfen.

Die Falltexte, Prompts, Varianten und Bewertungsregeln ändern sich nicht. Neu erzeugte PDF-Bytes und deren Hashes ändern sich; vorhandene Originale und Laufbelege bleiben erhalten.

## Vorbereitung des Hosting-Modus vom 29.10.2026

Zusätzlich zum PDF-Fix wurde ein expliziter Hosting-Modus mit denselben Python-Ausführungs- und Auswertungsmodulen vorbereitet. Der lokale Launcher bleibt unverändert.

- Unter Linux mit den gesperrten Abhängigkeiten: 270 Python-Tests erfolgreich mit einer nur unter Windows ausführbaren Auslassung; darunter elf neue Hosting-Tests für Authentifizierung, Origins, Hosts, CORS, Uploadgrenzen, geschützte Downloads, Neustart/Persistenz und Tokenrotation.
- 29 React-Tests sowie TypeScript-/Vite-Build für den lokalen und den Hosted-Modus erfolgreich. Ungültige HTTP-Konfiguration wurde erwartungsgemäß abgelehnt.
- Zwei tatsächliche HTTPS-Testserver mit verschiedenen Origins: zertifikatsgeprüfter HTTPx-Rundlauf für Projektpfad, Anmeldung, Preflight, PDF-Download/-Import/-Bestätigung, acht Mock-Läufe und Archiv erfolgreich. Dies ist kein Browsernachweis.
- Der lokale Playwright-Browserdownload scheiterte an einer unvollständigen ZIP-Datei. Deshalb werden die vorbereiteten zwei Hosted-Browsertests ausschließlich nach tatsächlich erfolgreicher GitHub-CI als bestanden bezeichnet. Der Pages-Workflow prüft Login, Downloads und Arbeitsablauf über getrennte HTTPS-Origins.
- Eine unabhängige technische Gegenprüfung wiederholte die elf Hosting- und 29 React-Tests. Externe HTTPS-Terminierung, Anbieter-Disk, produktive URL und Auto-Deployment bleiben nach der tatsächlichen Bereitstellung gesondert zu prüfen.

Keine echten Modellaufrufe, keine erfundenen Autorenbewertungen. Codeprüfung, Tests, Anbieterbereitstellung und fachliche Freigabe bleiben getrennte Nachweise.

## Kostenloser flüchtiger Testbetrieb vom 29.10.2026

Ausgangsstand: `c590dd45a96cc0ba687c794c55cf5d5e7eff623b`. Das Team wählte ausdrücklich einen kostenlosen Render-Webservice ohne dauerhafte Disk. Die Änderungen kennzeichnen diesen Speicherlebenszyklus; sie verändern weder Authentifizierung noch B/F/P/FP oder wissenschaftliche Urteile.

- Unter Linux die vollständige Python-Suite mit 271 Tests erfolgreich und einer ausschließlich unter Windows ausführbaren Auslassung. Die zwölf Hosting-Tests wurden zusätzlich gezielt ausgeführt. Hinzugekommen sind die geschützte Statusauskunft für lokale, persistente und flüchtige Arbeitsbereiche sowie die Ablehnung ungültiger `LAB_STORAGE_MODE`-Werte. Der öffentliche `/healthz`-Endpunkt bleibt minimal, die GUI bleibt mock-only.
- Nach `npm ci` alle 31 React-Tests erfolgreich. Der Hinweis zum Verlust von PDFs, Versuchen und Bewertungen erscheint im flüchtigen Modus und bleibt beim Seitenwechsel sichtbar. Im lokalen und persistenten Modus erscheint er nicht.
- TypeScript-/Vite-Builds für den lokalen Betrieb und den Hosted-Modus mit Pages-Unterpfad erfolgreich; `git diff --check` ohne Befund.
- Der lokale Hosted-Playwright-Aufruf startete die beiden HTTPS-Testserver, konnte aber beide Browserfälle wegen der fehlenden Chromium-Programmdatei nicht ausführen. Dies ist kein bestandener Browsertest. Die angepasste Browserfixture verwendet ausdrücklich flüchtigen Speicher und prüft den Warnhinweis bei jeder Anmeldung; ihr tatsächlicher CI-Status ist am endgültigen PR-Head zu prüfen.

Der Nutzer bestätigte den Ziel-Workspace `My Workspace`. Im angemeldeten Render-Dashboard wurden der Hobby-Plan, `No card on file` und keine ausstehenden Kosten tatsächlich geprüft. Das ist der Abrechnungsstand dieser Einrichtungsrunde, keine Zusage für spätere Kontoänderungen.

Eine laufende kostenlose Render-Ressource, die öffentliche Pages-Verbindung und das Verhalten unter der realen 512-MB-Grenze sind noch nicht nachgewiesen. Diese Live-Prüfungen bleiben vor einer Erfolgsmeldung erforderlich. Insbesondere ist weder ein Bedarf von 2 GB RAM noch die Eignung von 512 MB für beliebig große oder parallele PDF-Importe belegt. Es wurden keine Modellanfragen oder kostenpflichtigen Buchungen durchgeführt.

## Noch ausstehend

- Neue Oberfläche auf den weiteren Rechnern des Teams prüfen und die drei repräsentativen Fälle gemeinsam fachlich durchgehen.
- Synthetische PDF-Artikel und ihre Extraktionen inhaltlich prüfen; unter Windows besitzt der PDF-Worker noch kein hartes Betriebssystem-Speicherlimit.
- Eingerichtete und überprüfte äußere Isolation für echte Angriffsversuche.
- Auswahl, dokumentierte Preisprüfung und separater Pilot eines konkreten API-Modells.
- Unabhängige menschliche Bewertung, Entwicklung des getrennten Haupttestkatalogs, Einfrieren und Hauptmessung.

Der API-Adapter wurde ausschließlich mit simulierten Transportantworten geprüft. Es wurden keine echten API-Anfragen ausgeführt und keine Modellkosten verursacht. Budgetreservierungen sind lokale konservative Schätzungen auf Basis konfigurierter Preise, keine Zusage des Modellanbieters über einen absoluten Rechnungsbetrag.
