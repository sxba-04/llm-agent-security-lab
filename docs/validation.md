# Technischer Prüfstand vom 23. Oktober 2026

Diese Prüfungen betreffen die Implementierung. Sie sind keine empirischen Ergebnisse über die Angreifbarkeit eines Sprachmodells.

## Bestätigte Einrichtung beim Team

Sebastian hat die erfolgreiche Einrichtung des ursprünglichen Projektgerüsts auf seinem LUBW-Windows-Laptop in VS Code zurückgemeldet: Git, uv und Python sind installiert, die damaligen Start- und Prüfaufgaben wurden ausgeführt. Die neue React-Oberfläche wurde auf diesem Rechner noch nicht bestätigt. Sie benötigt zusätzlich Node.js 24 und den Frontend-Build. Jonahs Rechner und Sebastians private Rechner bleiben gesondert zu prüfen.

## Lokal ausgeführte Prüfungen

- Python 3.12.14 unter Linux; `uv sync --locked --extra web --group dev` erfolgreich.
- 225 Python-Tests erfolgreich, einschließlich FastAPI-TestClient und tatsächlicher PDF-Extraktion im Unterprozess.
- Zwölf React-Verhaltenstests erfolgreich: kein Start beim Laden/Neuladen, expliziter Start mit Sitzungstoken, getrennte Bewertungsplätze ohne voreingestellte Urteile, Bestätigung des konkreten PDF-Texthashes, inerte Darstellung von Angriffstexten, eingefrorene Bewertungen, Isolation beschädigter Kampagnen und Aktualisierung des Vergleichs bis zum Serienabschluss.
- TypeScript-Prüfung und Vite-Produktionsbuild erfolgreich (Node.js 24).
- Alle zwölf überarbeiteten Entwicklungspaare strukturell validiert; alle 24 Beispiel-PDFs behalten ihre relevanten Textinhalte.
- Vollständiger Entwicklungskatalog: zwölf Paare, vier Varianten, zwei Quellfassungen und drei Wiederholungen ergeben 288 von 288 abgeschlossene Mock-Läufe.
- Kampagne exportiert, alle 579 Dateien verifiziert, wiederhergestellt und Zusammenfassung samt CSV aus den wiederhergestellten Originalen neu berechnet. Archivbericht: Integrität geprüft, Belegdateien vollständig; keine Signatur oder Urheberschaftsprüfung.
- Export, zwei synthetische Testbewertungen, Zusammenführung und begründete Klärung im Integrationstest geprüft. Es wurden keine menschlichen wissenschaftlichen Bewertungen erfunden.

## Gegenprüfungen und CI

Unabhängige technische Gegenprüfungen betrafen Adapter-/Antwortfehler, Provenienz, Paarbarkeit, Archive sowie die lokalen HTTP- und PDF-Grenzen. Bestätigte Befunde wurden mit Regressionstests korrigiert. Der anschließende GitHub-Review ergab zusätzliche Korrekturen an einmaliger Zusammenführung, gemeinsamer Adjudikation, laufenden CLI-Serien, Wiederherstellungsbelegen und beschädigten beziehungsweise verwaisten UI-Kampagnen. Zusätzliche Korrekturen prüfen sämtliche archivierten Bewertungsstände samt Original-CSV und Vorgängern, halten die Vergleichsansicht aktuell und vermeiden wiederholtes Einlesen unveränderter Kampagnen beim Polling. Die Artikelfakten wurden auf eigenständigen Informationsgehalt präzisiert; anschließend wurden erneut 288 Mock-Läufe und der vollständige Archivablauf geprüft. Ein echter Unterprozess-Test prüft dabei einen lebenden fremden Worker und die Wiederherstellung nach dessen erzwungenem Ende. Insbesondere dürfen abweichende Ausgangsdaten nicht gepaart, fremde Review-Pakete nicht einer Kampagne zugeordnet und fehlende Ereignisduplikate nicht als vollständig ausgegeben werden. Sicherheits- und Proxyprüfungen schließen fremde Hosts/Origins, fehlende Token, Pfadwechsel und parallele Serienstarts ein.

Der lokale Browserdownload war in dieser Arbeitsumgebung nicht erreichbar. Beide echten Chromium-Browsertests bestanden anschließend auf GitHub und erneut zusammen mit 206 Python-Tests unter Windows/Linux und elf React-Tests am Commit `efc6abb`: [CI-Durchlauf](https://github.com/sxba-04/llm-agent-security-lab/actions/runs/39927902245). Geprüft wurden expliziter Start, acht Läufe, Neuladen ohne Doppelstart, Ereignis-/Ticketansicht, Vergleiche, PDF-Download/Import/Bestätigung, getrennte Bewertungsentwürfe und mobile Navigation. Die Desktop- und Mobile-Screenshots wurden visuell geprüft. Deshalb wird kein lokal bestandener Chromium-Test behauptet. GitHub Actions führt die Python-Prüfungen unter Windows und Linux sowie React-Tests, Build und einen echten Browserdurchlauf mit FastAPI aus. Der jeweilige Status ist am aktuellen PR-Commit zu prüfen; vorbereitete CI allein ist kein Erfolgsnachweis. Browserberichte und Screenshots werden als CI-Artefakte gespeichert.

## Noch ausstehend

- Neue Oberfläche auf den konkreten Windows-Rechnern des Teams einschließlich Firmenproxy starten und die drei repräsentativen Fälle gemeinsam fachlich durchgehen.
- Synthetische PDF-Artikel und ihre Extraktionen inhaltlich prüfen; unter Windows besitzt der PDF-Worker noch kein hartes Betriebssystem-Speicherlimit.
- Eingerichtete und überprüfte äußere Isolation für echte Angriffsversuche.
- Auswahl, dokumentierte Preisprüfung und separater Pilot eines konkreten API-Modells.
- Unabhängige menschliche Bewertung, Entwicklung des getrennten Haupttestkatalogs, Einfrieren und Hauptmessung.

Der API-Adapter wurde ausschließlich mit simulierten Transportantworten geprüft. Es wurden keine echten API-Anfragen ausgeführt und keine Modellkosten verursacht. Budgetreservierungen sind lokale konservative Schätzungen auf Basis konfigurierter Preise, keine Zusage des Modellanbieters über einen absoluten Rechnungsbetrag.
