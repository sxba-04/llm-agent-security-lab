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
uv run python -m unittest discover -s tests -v
git status
git diff
git add <gepruefte-dateien>
git commit -m "Beschreibt die konkrete Änderung"
git push -u origin feat/kurze-aufgabe
```

`<gepruefte-dateien>` ist ein Platzhalter und wird durch die tatsächlich geprüften Pfade ersetzt. Vor dem Commit kontrollieren, dass keine Schlüssel, lokalen Einstellungen oder unbeabsichtigten Laufdaten enthalten sind.

Ein Pull Request beschreibt Problem, Änderung, erwartetes Verhalten und Prüfung. Die andere Person prüft insbesondere Berechtigungsgrenzen, vergleichbare Bedingungen und den Bezug zum Versuchsplan. Erst anschließend wird zusammengeführt. Ein eigener dauerhafter `develop`-Branch ist für diesen Umfang nicht nötig.

Technisch erzwungene Branchregeln hängen vom GitHub-Tarif und den Repository-Einstellungen ab. Die gemeinsame Review-Regel gilt unabhängig davon.

## Parallel arbeiten

Gemeinsame Schnittstellen zuerst kurz festlegen. Die Aufgaben danach nach Komponenten aufteilen, beispielsweise Anwendung und Policy gegenüber Fallkatalog und Auswertung. Beide Personen übernehmen praktische und wissenschaftliche Tätigkeiten. Änderungen am selben Kern werden abgestimmt, bevor zwei parallele Umbauten entstehen.

Bei Nutzung mehrerer Rechner vor einem Wechsel committen und pushen; auf dem nächsten Rechner zuerst den aktuellen Stand holen. Lokale API-Schlüssel und virtuelle Umgebungen verbleiben auf dem jeweiligen Rechner.

## Messstände sichern

Ein Messstand umfasst Code, Konfiguration, Fälle, Manifest, Rohlogs und Bewertung. Ein Commit oder Tag allein enthält keine ignorierten Laufdaten. Diese werden als vollständiges, unverändertes Reproduktionspaket zusätzlich gesichert.

Vor dem Hauptversuch muss ein sauberer Arbeitsstand vorliegen. Nachträgliche Änderungen an Modell, Filter, Policy, Fällen oder Bewertungsregeln erzeugen eine getrennte Serie. Ergebnisse werden nicht nachträglich einem anderen Codezustand zugeordnet.

## Fertigkriterien

- Der Ablauf ist aus einem frischen Klon reproduzierbar beschrieben.
- Erlaubte und unerlaubte Aktionen wurden an geeigneten Grenzfällen geprüft.
- Vorschlag, Entscheidung und Wirkung bleiben in den Logs unterscheidbar.
- Neue Messgrößen sind aus den gespeicherten Rohdaten ableitbar.
- Dokumentation, Beitragseintrag und tatsächlicher Prüfstatus stimmen überein.
