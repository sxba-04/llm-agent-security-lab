# Sonar-Inventuren und Einzelprüfungen

## Belegter Snapshot vom 2. November 2026

Die erneute schreibgeschützte Inventur meldet **177 offene Befunde** für `main`.
Sie wurde am **02.11.2026 um 01:07:27 MEZ** (00:07:27 UTC) erhoben:
[Workflow-Lauf 41260073281, Versuch 2](https://github.com/sxba-04/llm-agent-security-lab/actions/runs/41260073281/attempts/2),
Artefakt `sonar-main-inventory`, ID `13107111361`, ZIP-SHA-256
`b557aef35278e2e96caa4926ac515545c17d29902465daa7b49613f8b82ea14d`.
Das Artefakt wird nach 14 Tagen gelöscht; diese Angaben sichern seine Herkunft,
ersetzen aber keinen aufbewahrten Export.

Die enthaltene Sonar-Analyse `66c95360-ccb2-43be-a05d-760a1c64c865` bezieht sich
auf **`5e192a2567cc9be33219247b8b4cc9aec4324662`**, analysiert am
01.11.2026 um 23:32:58 UTC. Der erneut gestartete Inventur-Workflow selbst stammt
von einem älteren Checkout; maßgeblich ist ausdrücklich die Analyse-Revision im
JSON. Spätere Änderungen sind nicht in diesen 177 Befunden enthalten.

| Messwert aus diesem Snapshot | Wert |
|---|---:|
| Offene Befunde (`resolved=false`) | 177 |
| Scanner-Typ `CODE_SMELL` | 158 |
| Scanner-Typ `VULNERABILITY` | 18 |
| Scanner-Typ `BUG` | 1 |
| Quality Gate | OK |
| Gesamte Sonar-Coverage | 85,4 % |
| Zeilenabdeckung | 89,3 % |
| Zweigabdeckung | 78,2 % |
| Coverage des neuen Codes | 96,8 % |

Scanner-Typen sind keine bestätigten Sicherheitsurteile. Von den 177 IDs sind
175 im historischen Ledger enthalten: 152 dort als Wartbarkeitsschuld, 21 als
False Positive und zwei als beabsichtigte Verwendung bewertet. Keine damals als
`addressed` bewertete ID ist noch offen. Die zwei neuen IDs sind
`AaGZev26WV1cgC4s9_Ep` (`mock-campaign.yml:91`) und
`AaGZev2nWV1cgC4s9_Eo` (`tests.yml:124`), jeweils `githubactions:S7689`.
Sie betreffen Markdown-Backticks in Python-Strings und sind nach Quellprüfung
False-Positive-Kandidaten; die korrigierte Regelbedeutung steht im [CI-Bericht](ci.md).
Sie werden nicht in die historische 230er-Inventur eingefügt.

### Nachprüfung der 18 Vulnerability- und einer Bug-Markierung

Die gemeldeten Datenflüsse wurden am 02.11.2026 erneut am Quellcode geprüft.
Die 14 S8707-Flows erhielten zusätzlich eine unabhängige Agenten-Gegenprüfung.
Dabei wurde in diesen konkreten Traces keine bestätigte Schwachstelle gefunden;
das ist keine Aussage über eine vollständig sichere Anwendung und kein
Remote-Abschluss der Scannerbefunde.

| Regel / Anzahl | Quellbefund und Einordnung |
|---|---|
| `pythonsecurity:S8707` / 14 | `archives.py`, `batch.py`, `cases.py` und `review.py`: Die jeweils gemeldeten äußeren Lese-/Schreibpfade kommen aus ausdrücklichen CLI-Operatorargumenten. Artikel, Modellantworten oder ZIP-/CSV-/JSON-Inhalte bestimmen diese Argumente nicht. Beleg-Unterpfade werden zusätzlich begrenzt; der Webpfad bildet seine Ziele separat im verwalteten Workspace. Die dokumentierte False-Positive-Einordnung gilt für genau diese Flows. |
| `python:S5332` / 1 | `server.py`: `http://` wird nur für `urlsplit` des Host-Headers verwendet. Der Parser öffnet keine Netzwerkverbindung. Kontextueller False Positive; Host-/Origin-Prüfungen bleiben erforderlich. |
| `python:S4830` / 1 | `providers.py`: Der tatsächlich an `HTTPSHandler` übergebene Kontext stammt aus `ssl.create_default_context()`; Zertifikats- und Hostnamenprüfung werden nicht deaktiviert. Kontextueller False Positive. |
| `python:S8392` / 1 | `hosted_cli.py`: `0.0.0.0` ist die bewusste Bindung des separat aktivierten, authentifizierten Hosted-Modus hinter dem HTTPS-Proxy. Beabsichtigte Verwendung unter diesen Betriebsannahmen; der lokale Launcher bleibt auf Loopback. |
| `python:S2245` / 1 | `batch.py`: `random.Random(seed).shuffle` randomisiert reproduzierbar die Versuchsreihenfolge. Es erzeugt weder Zugangstoken noch kryptographische Schlüssel. Beabsichtigte Verwendung. |
| `python:S2201` / 1 Bug | `batch.py`: Der ungenutzte Rückgabewert von `extracted.decode("utf-8")` ist beabsichtigt; die Operation validiert gespeicherte Bytes und muss bei ungültigem UTF-8 scheitern. Originalbytes und Hashes bleiben erhalten. Kontextueller False Positive. |

Diese Nachprüfung umfasst Quellcode und Aufrufgrenzen, keine neu ausgeführten
Laufzeittests und keine vollständige Prüfung aller möglichen Helfer-Nutzungen
oder lokalen Dateisystemrennen. Die Herkunftsdateien `archives.py`, `batch.py`,
`cases.py`, `review.py`, `cli.py`, `providers.py` und `hosted_cli.py` waren dabei
gegenüber dem Analyse-Commit unverändert; bei `server.py` wurde zusätzlich der
aktuelle, verhaltensbewahrend ausgelagerte Host-Parser geprüft. Neue Codeänderungen
benötigen ihre eigene CI und Sonar-Analyse. Kein Befundstatus wurde durch diese
Nachprüfung in Sonar geändert.

## Historische Einzelprüfung vom 1. November 2026

Die damalige Prüfung umfasst **alle 230 offenen Befunde** der Inventur aus
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

| Ursprüngliches Ergebnis vom 01.11.2026 | Anzahl | Bedeutung |
|---|---:|---|
| Durch Änderungen adressiert | 49 | Fehlerkorrekturen, gezielte Härtungen und klarere Tests; endgültigen Scannerstatus der neuen Analyse entnehmen |
| Kontextuelle Fehlalarme | 26 | Konkrete Datenflüsse, vorhandene Schutzprüfungen oder tatsächlich funktionierende UI-Semantik dokumentiert |
| Begründete Verwendung | 2 | Öffentliche Bindung im ausdrücklich aktivierten Hosted-Modus und reproduzierbare Zufallsreihenfolge der synthetischen Studie |
| Verbleibende Wartbarkeitshinweise | 153 | Unter anderem Komplexität, verschachtelte Ausdrücke, readonly-Props, wiederholte Literale und interne API-Fehlerdokumentation |
| **Gesamt** | **230** | Vollständiger abgeglichener Inventurbestand |

Diese Zahlen und [summary.json](summary.json) bewahren die ursprüngliche
Zusammenführung vom 01.11.2026 vor der datierten S7689-Korrektur im [CI-Bericht](ci.md).
Zwei damals als adressiert eingeordnete Meldungen wurden dort als kontextuelle
False Positives neu bewertet; die alten Bewertungen bleiben in `ci.json` erhalten.
Die historischen Zahlen werden nicht mit dem neuen 177er-Snapshot vermischt und
sind keine aktuelle Anzeige der Sonar-Oberfläche. Eine Korrektur kann mehrere
Meldungen adressieren;
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
