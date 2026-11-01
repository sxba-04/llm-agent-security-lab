# Sonar-Einzelprüfung vom 1. November 2026

Die Prüfung umfasst **alle 230 offenen Befunde** der Inventur aus
[Workflow-Lauf 41257152584](https://github.com/sxba-04/llm-agent-security-lab/actions/runs/41257152584).
Die Sonar-Analyse bezieht sich auf Commit
`12db393771b70f05f12f947fe213c43084a0fce5`; die Quellprüfung erfolgte zunächst
gegen `3731bcd9a86fd98aca9c8168c9b1bf8065b44d62`. Die betroffenen Quellstellen
waren zwischen diesen Ständen unverändert. Spätere Abhängigkeitsupdates und
Korrekturen werden zusätzlich durch die CI des jeweiligen PR-Heads geprüft.

Jede Inventurkennung ist genau einmal einem Bericht zugeordnet. Ein Abgleich
von Kennung, Regel, Datei und ursprünglicher Zeile ergab 230 Übereinstimmungen,
keine fehlenden und keine doppelten Kennungen. Die ursprünglichen Positionen
werden als Herkunftsnachweis bewahrt; nach Änderungen können sich Zeilen ändern.

| Ergebnis der Einzelprüfung | Anzahl | Bedeutung |
|---|---:|---|
| Durch Änderungen adressiert | 49 | Fehlerkorrekturen, gezielte Härtungen und klarere Tests; endgültigen Scannerstatus der neuen Analyse entnehmen |
| Kontextuelle Fehlalarme | 26 | Konkrete Datenflüsse, vorhandene Schutzprüfungen oder tatsächlich funktionierende UI-Semantik dokumentiert |
| Begründete Verwendung | 2 | Öffentliche Bindung im ausdrücklich aktivierten Hosted-Modus und reproduzierbare Zufallsreihenfolge der synthetischen Studie |
| Verbleibende Wartbarkeitshinweise | 153 | Unter anderem Komplexität, verschachtelte Ausdrücke, readonly-Props, wiederholte Literale und interne API-Fehlerdokumentation |
| **Gesamt** | **230** | Vollständiger abgeglichener Inventurbestand |

Diese Zahlen sind Bewertungen des angegebenen Ausgangsbestands, keine aktuelle
Anzeige der Sonar-Oberfläche. Eine Korrektur kann mehrere Meldungen adressieren;
ein Befund kann eine sinnvolle Härtung beschreiben, ohne einen beobachteten
Angriff nachzuweisen. Es wurden keine Sonar-Befunde per API geschlossen oder als
akzeptiert markiert. Die neue Analyse entscheidet, welche Befunde automatisch
als behoben erscheinen. Sonars Quell-/Testzuordnung kann außerdem die Menge
gegenüber der früheren automatischen Konfiguration verändern.

## Vollständige Einzelbewertungen

| Bereich | Befunde | Bericht | Maschinenlesbare Einzelbelege |
|---|---:|---|---|
| Backend, Hosting, Pfade und Archive | 66 | [Backend](backend.md) | [backend.json](backend.json) |
| React/TypeScript und Browser-Testquellen | 92 | [Frontend](frontend.md) | [frontend.json](frontend.json) |
| Übriger Python-Code und Python-Testbefunde | 53 | [Python](python-other.md) | [python-other.json](python-other.json) |
| GitHub Actions und CI-Hilfsskript | 19 | [CI](ci.md) | [ci.json](ci.json) |

[summary.json](summary.json) enthält die Zusammenführung mit jeder Kennung,
Berichtszuordnung und Maßnahme sowie Analysekennung, Datum und SHA-256 des
abgerufenen Inventurartefakts. Die Detailberichte bewahren ihre lokalen
Prüfzeitpunkte und Grenzen. Verbindlich für einen Merge sind die aktuellen
GitHub-Prüfungen und abgeschlossenen Reviews des endgültigen Heads.

## Bestätigte Fehler und geprüfte Grenzen

- Der Archivexport veröffentlichte zuvor den endgültigen ZIP-Namen während
  eines Kopiervorgangs. Ein Speicherfehler konnte ein unvollständiges Ziel
  zurücklassen und einen erneuten Export blockieren. Jetzt wird erst das
  vollständig geschriebene, geprüfte und synchronisierte Archiv atomar ohne
  Überschreiben veröffentlicht. Fehler-, Konkurrenz- und Wiederholungstests
  prüfen diese Grenze. Hardlink-Unterstützung bleibt erforderlich.
- Nicht-ASCII-Bytes im lokalen Mutationstoken verursachten einen HTTP-500-Fehler.
  Der Bytevergleich weist sie mit HTTP 403 ab, ohne einen Versuch zu starten.
  Das war kein nachgewiesener Authentifizierungs-Bypass. Dieser Fehler wurde
  zusätzlich bei der Quellprüfung gefunden, nicht einer Sonar-Kennung zugeschrieben.
- Gefilterte Vergleichskarten konnten den geöffneten Detailzustand einer anderen
  Karte übernehmen. Fachlich stabile React-Keys erhalten die richtige Zuordnung;
  ein Regressionstest reproduziert den ursprünglichen Fehler.
- Die PDF-Erzeugung sammelte Absatzzeilen mit quadratisch wachsendem Kopieraufwand.
  Die lineare Zusammenstellung erhält die Ausgabe; 25 lokal verglichene PDFs
  waren bytegleich. Die vorhandenen Rendering- und Extraktionstests bleiben aktiv.

Die CI erzwingt Wheels beim uv-Bootstrap und unterbindet fremde Python-Source-
Builds sowie npm-Installationsskripte. Das eigene ausgecheckte Python-Projekt
bleibt als Editable-Build zulässig. Playwright wird aus dem gesperrten lokalen
Paket gestartet. Die Zusammenfassungen lesen den tatsächlich ausgecheckten
Commit; bei PR-Tests ist dies weiterhin der getestete Merge-Commit.

Zusätzliche Fehlerpfadtests prüfen unter anderem manipulierte Dokument- und
Frontendpfade, Symlinks, ungültiges UTF-8 in korrekt gehashten Archivdateien und
Zertifikatsfehler ohne Wiederholung oder Offenlegung des simulierten API-Schlüssels.
Die explizite TLS-1.2-Mindestversion der HTTPS-Test-Fixture verdeutlicht den unter
Python 3.12 bereits vorhandenen sicheren Standard.

## Aussagegrenzen und weitere Arbeit

Der öffentlich verfügbare genaue Regeltext von `pythonsecurity:S8707` konnte
nicht verifiziert werden. Die 17 betroffenen Datenflüsse wurden anhand ihrer
Positionen und des Quellcodes einzeln geprüft; die Berichte erfinden weder
Diagnosetexte noch Regelbeschreibungen. Eine spätere Sonar-interne Gegenprüfung
kann diese dokumentierten Bewertungen ergänzen.

Die verbleibenden Wartbarkeitshinweise sind konkrete weitere Aufgaben. Größere
Refactorings sollten eigene, verhaltensbewahrende PRs erhalten, besonders für
Archiv-/Bewertungslogik und komplexe UI-Ausdrücke. Die experimentellen Varianten
B/F/P/FP, Auswertung und Originalbelege wurden nicht umdefiniert. Mock-Tests sind
technische Prüfungen und keine empirischen LLM-Ergebnisse.

Die separat geprüften 23 CodeQL-Meldungen stehen im
[CodeQL-Bericht](../codeql-triage-2026-11-01.md). Für wichtige Daten gilt die
gewählte [Routine für lokale Kampagnenarchive](../archives.md); Render bleibt
eine flüchtige Testumgebung.
