# Zusammenarbeit und Versionierung

Beide Autoren arbeiten mit eigenen GitHub-Konten und lokalen Klonen. `main` enthält den gemeinsam nachvollziehbaren Stand. Eine Aufgabe erhält eine verantwortliche Person, ein erwartetes Ergebnis und ein überprüfbares Fertigkriterium.

## Änderung bearbeiten

```powershell
git switch main
git pull --ff-only
git switch -c feat/kurze-aufgabe
```

Nach der Änderung werden die entscheidenden Tests ausgeführt und die Dokumentation angepasst:

```powershell
uv sync --locked --extra web --group dev
uv run --locked --extra web python -m unittest discover -s tests -v
git status
git diff
git add <gepruefte-dateien>
git commit -m "Beschreibt die konkrete Änderung"
git push -u origin feat/kurze-aufgabe
```

`<gepruefte-dateien>` ist ein Platzhalter und wird durch die tatsächlich geprüften Pfade ersetzt. Vor dem Commit kontrollieren, dass keine Schlüssel, lokalen Einstellungen oder unbeabsichtigten Laufdaten enthalten sind.

Ein Pull Request beschreibt Problem, Änderung, erwartetes Verhalten und Prüfung. Die andere Person prüft insbesondere Berechtigungsgrenzen, vergleichbare Bedingungen und den Bezug zum Versuchsplan. Erst anschließend wird zusammengeführt. Ein eigener dauerhafter `develop`-Branch ist für diesen Umfang nicht nötig.

## Verbindlicher Abschluss eines Pull Requests

Vor dem Merge werden die Windows-/Linux- und gegebenenfalls Frontend-Prüfungen sowie die angeforderten inhaltlichen Reviews abgewartet. Ein gestarteter Review und ein grüner Testlauf sind noch kein abgeschlossener Review. Der geprüfte Commit muss dem aktuellen PR-Head entsprechen. Nach einer Korrektur werden die betroffenen Tests erneut ausgeführt und die geänderten Stellen nochmals geprüft; veraltete Review-Ergebnisse werden nicht als Freigabe des neuen Stands dargestellt.

Code-Review, Security-Review und CI sind getrennte Nachweise. Ein Kontingent- oder Authentifizierungsfehler ist keine erfolgreiche Prüfung und auch kein fachlicher Sicherheitsbefund. Er wird im PR dokumentiert. Sebastian hat ausdrücklich freigegeben, bei ausgeschöpftem Copilot-Kontingent ohne eine erneute Copilot-Prüfung zusammenzuführen, wenn die CI, Codex-Code- und Security-Reviews am aktuellen Commit erfolgreich abgeschlossen sind und eine unabhängige technische Gegenprüfung vorliegt. Das ist keine pauschale Ausnahme für andere fehlgeschlagene Reviews. Ein nicht verfügbarer Dienst wird nicht ohne neue Ursache wiederholt angefordert.

Jeder Befund erhält eine nachvollziehbare Behandlung: behoben und nachgeprüft oder mit konkreten Belegen als nicht zutreffend beziehungsweise bewusst begrenzt eingeordnet. Ein Thread wird nicht allein deshalb geschlossen, weil der ursprüngliche PR bereits gemergt ist. PR #1 wurde am 22.10.2026 vor Ende der automatischen Reviews zusammengeführt; dieser Ablauf wird nicht wiederholt.

Die Checkliste in der PR-Vorlage unterstützt diesen Prozess. Seit 29.10.2026 erzwingt das aktive [Ruleset für `main`](branch-protection.md) Pull Requests, vier aktuelle Windows-/Linux-Checks und erledigte Review-Gespräche; Force-Push und Löschen sind gesperrt. Es gibt keine Bypass-Liste. Die technisch geforderten CI-Checks ersetzen die inhaltlichen Codex-Reviews und fachlichen Autorenprüfungen nicht.

[GitHub Actions](github-actions.md) beschreibt die Tests, Ergebnisartefakte und manuell startbaren Mock-Kampagnen. Die [gemeinsame Abnahme](manual-acceptance.md) ergänzt diese technischen Nachweise durch eure tatsächlichen Beobachtungen und fachlichen Entscheidungen.

## Parallel arbeiten

Gemeinsame Schnittstellen zuerst kurz festlegen. Die Aufgaben danach nach Komponenten aufteilen, beispielsweise Anwendung und Policy gegenüber Fallkatalog und Auswertung. Beide Personen übernehmen praktische und wissenschaftliche Tätigkeiten. Änderungen am selben Kern werden abgestimmt, bevor zwei parallele Umbauten entstehen.

Bei Nutzung mehrerer Rechner vor einem Wechsel committen und pushen; auf dem nächsten Rechner zuerst den aktuellen Stand holen. Lokale API-Schlüssel und virtuelle Umgebungen verbleiben auf dem jeweiligen Rechner.

Lokaler Codex, ChatGPT Work und die GitHub-Review-Bots arbeiten nicht automatisch auf demselben lokalen Dateistand. Für Übergaben maßgeblich sind Repository, Branch, Commit und reproduzierbare Prüfnachweise. Nicht gepushte Änderungen und lokale Laufdaten werden durch denselben OpenAI-Account nicht automatisch synchronisiert. Credits für Entwicklungs- und Review-Werkzeuge werden getrennt vom API-Budget der späteren Laborversuche betrachtet.

`AGENTS.md` enthält Arbeitsregeln für Entwicklungsagenten. `SECURITY.md` beschreibt Sicherheitsinvarianten und die Einordnung von Befunden; `docs/threat-model.md` erläutert die konkreten Datenflüsse. Diese Dateien konfigurieren keine Kontingente oder kostenpflichtigen Kontoeinstellungen. Ihre Inhalte müssen bei Änderungen an Werkzeugen, Betriebsart oder Vertrauensgrenzen mitgeprüft werden.

## Messstände sichern

Ein Messstand umfasst Code, Konfiguration, Fälle, Manifest, Rohlogs und Bewertung. Ein Commit oder Tag allein enthält keine ignorierten Laufdaten. Diese werden als vollständiges, unverändertes Reproduktionspaket zusätzlich gesichert.

Vor dem Hauptversuch muss ein sauberer Arbeitsstand vorliegen. Nachträgliche Änderungen an Modell, Filter, Policy, Fällen oder Bewertungsregeln erzeugen eine getrennte Serie. Ergebnisse werden nicht nachträglich einem anderen Codezustand zugeordnet.

## Fertigkriterien

- Der Ablauf ist aus einem frischen Klon reproduzierbar beschrieben.
- Erlaubte und unerlaubte Aktionen wurden an geeigneten Grenzfällen geprüft.
- Vorschlag, Entscheidung und Wirkung bleiben in den Logs unterscheidbar.
- Neue Messgrößen sind aus den gespeicherten Rohdaten ableitbar.
- Dokumentation, Beitragseintrag und tatsächlicher Prüfstatus stimmen überein.
