# Wartungsstand vom 2. November 2026

Dieser Bericht dokumentiert den geprüften Stand nach PR #19 und PR #20 auf
`main` bei `9027b9833b2bab8e518005032cfbc2bc530ea023`. Er ist eine zeitgebundene
Betriebs- und Qualitätsprüfung, keine wissenschaftliche Bewertung der
Schutzmaßnahmen und keine Zusage, dass sämtliche Scannerbefunde erledigt sind.
Die anschließende zweite Bereinigungsrunde auf `codex/quality-follow-up`
ist getrennt unter „Lokale Folgeprüfung“ dokumentiert. Sie ist in den folgenden
veröffentlichten Ergebnissen und Sonar-Zahlen noch nicht enthalten.

## Abgeschlossene Änderungen und Veröffentlichung

| Bereich | Verifizierter Stand |
|---|---|
| [PR #19](https://github.com/sxba-04/llm-agent-security-lab/pull/19) | Sicherheitsupdate von `pypdf` 6.21.2 auf 6.21.4 geprüft und gemergt; vor dem Merge mit aktuellem `main` zusammengeführt und erneut geprüft. |
| [PR #20](https://github.com/sxba-04/llm-agent-security-lab/pull/20) | Sitzungsbehandlung, Wartbarkeit, Regressionstests und Betriebsdokumentation geprüft und gemergt. |
| GitHub Actions | Die Prüfungen des genannten `main`-Commits sind abgeschlossen und erfolgreich; [Tests, Sonar und Inventur](https://github.com/sxba-04/llm-agent-security-lab/actions/runs/41368284425). |
| GitHub Pages | Der genannte Commit wurde durch den [Pages-Durchlauf](https://github.com/sxba-04/llm-agent-security-lab/actions/runs/41368284230) veröffentlicht. |
| Render | Deployment `dep-dbjtsivb9u1s73c583u0` desselben Commits ist seit 02.11.2026, 01:51:23 MEZ (00:51:23 UTC), `live`. |
| Compute und Datenhaltung | Bestehender Plan `0.5c-512mb`: 0,5 CPU, 512 MB RAM; weiterhin flüchtiger Workspace ohne neu eingerichtete Disk. |

Die Sitzungsänderung unterscheidet den persönlichen Zugangscode vom internen
Token für schreibende Anfragen. Nach einem Serverneustart wird eine mit altem
Sitzungstoken abgewiesene Aktion nicht automatisch wiederholt. Der Client zeigt
den Grund an; eine anschließend bewusst ausgelöste Aktion lädt zuerst ein
neues Sitzungstoken. Der weiterhin gültige persönliche Code muss dafür nicht
nochmals eingegeben werden. Ein verlorener persönlicher Code bleibt dagegen
nur durch kontrollierte Rotation ersetzbar.

Die Dokumentation erläutert das bestehende Python-`src`-Layout, enthält einen
[zentralen Einstieg](README.md) und [vorbereitete Wiki-Quellen](wiki/README.md).
Die technischen Anleitungen bleiben mit dem Code versioniert. Die
[Hosting-Anleitung](hosting.md) trennt Compute-Upgrade, dauerhafte Speicherung,
Zugangswiederherstellung und einen möglichen späteren Konto-Login.

## Tests und Coverage

Die CI des festgehaltenen Commits prüfte die Python-Suite mit 306 Testfällen und
43 React-Tests. Die Windows-/Linux-Jobs, Produktionsbuilds und vorgesehenen
Browserprüfungen waren erfolgreich. Plattformabhängige Auslassungen in den
jeweiligen Joblogs bleiben Auslassungen; der Linux-Lauf ersetzt keinen
Windows-Nachweis. Alle Testläufe verwenden synthetische Daten und keinen echten
Modellanbieter.

Die folgenden Quoten stammen aus den Linux-Coverage-Artefakten desselben
[Testdurchlaufs](https://github.com/sxba-04/llm-agent-security-lab/actions/runs/41368284425):

| Messung | Zeilen | Zweige |
|---|---:|---:|
| Python (`coverage.py`) | 3.391 / 3.768 = **89,99 %** | 1.171 / 1.428 = **82,00 %** |
| React/TypeScript (V8) | 484 / 526 = **92,01 %** | 720 / 907 = **79,38 %** |

Sonar importiert diese Berichte und berechnet eigene Metriken auf seinem
konfigurierten Quellumfang. Sein Snapshot weist **87,1 % Gesamt-Coverage**,
90,3 % Zeilen-Coverage und 81,0 % Zweig-Coverage aus. Das Main-Quality-Gate meldet
**90,6 % Coverage für neuen Code** und Status `OK`. Diese Zahlen dürfen weder
untereinander noch mit einer einzelnen Python- oder React-Zeilenquote
gleichgesetzt werden. Browser- und Unterprozesstests werden nicht nachträglich
in die Unit-Coverage hineingerechnet. Eine hohe Quote ersetzt keine passenden
Assertions und keine Prüfung relevanter Fehlerpfade.

## Sonar: Zeitpunkt und Vergleichsgrundlage

Die Inventur enthält ausschließlich ungelöste Befunde auf `main` des Projekts
`sxba-04_llm-agent-security-lab`. Sie exportiert keine PR- oder geschlossenen
Befunde. Die erfasste Analyserevision und die einzelnen Issue-Kennungen bilden
die Vergleichsgrundlage. Die zuvor genannten 178 Meldungen konnten in dieser
Abfrage nicht reproduziert werden; Vergleichsbasis ist das erfasste
177-Befunde-Inventar.

| Beobachtung | Vor der Wartung | Nach PR #20 |
|---|---|---|
| Analyserevision | `5e192a2567cc9be33219247b8b4cc9aec4324662` | `9027b9833b2bab8e518005032cfbc2bc530ea023` |
| Von Sonar gemeldeter Analysezeitpunkt | 01.11.2026, 23:32:58 UTC | 02.11.2026, 00:44:15 UTC |
| Zeitpunkt des Inventurabrufs | 02.11.2026, 00:07:27 UTC | 02.11.2026, 00:50:12 UTC |
| Ungelöste Kennungen | 177 | **79** |

Der gemeldete Analysezeitpunkt liegt vor dem erfolgreichen Abschluss des Scans;
der Inventurabruf erfolgte danach. Alle Uhrzeiten in dieser Tabelle
sind ausdrücklich UTC; am 2. November entspricht MEZ jeweils UTC plus einer
Stunde. Der aktuelle Export ist als Artefakt `sonar-main-inventory`
(ID `13109035398`) im oben verlinkten Actions-Durchlauf enthalten. CI-Artefakte
werden zeitlich begrenzt aufbewahrt; dieser Bericht hält die ausgewerteten
Kennzahlen und Revisionsbezüge fest.

Der Vergleich der Kennungen ergibt **98 nicht mehr im ungelösten Bestand
enthaltene Befunde und keine neuen Kennungen**. Die 79 verbliebenen Kennungen
waren bereits im Ausgangsinventar enthalten. Das ist stärker als ein bloßer
Vergleich zweier Summen, beweist aber keine allgemeine Fehlerfreiheit. Eine
lesende Inventur ist zudem keine unveränderliche Serverkopie: parallele
Statusänderungen wären grundsätzlich möglich. In dieser Wartungsrunde wurden
Sonar-Befunde nicht manuell geschlossen, akzeptiert oder als False Positive
markiert; die aktiven Regeln wurden nicht pauschal unterdrückt.

Der geprüfte PR-Stand `15499e4` meldete **null neue PR-Befunde**. Der anschließende
Main-Check bezeichnet dagegen 79 Befunde im dort geltenden New-Code-Zeitraum
als neu. PR-Differenz und Main-New-Code-Zeitraum haben verschiedene
Vergleichsgrenzen. Die genaue serverseitige Periodenkonfiguration konnte über
die zugängliche Schnittstelle nicht gelesen werden; sie wird hier nicht
behauptet. Ein grünes PR- oder Main-Gate bedeutet deshalb nicht null
ungelöste Gesamtbefunde.

## Verbleibende Befunde und ihre Einordnung

| Sonar-Typ im Snapshot | Anzahl | Bedeutung dieser Zahl |
|---|---:|---|
| `CODE_SMELL` | 61 | Scannerhinweise zur Wartbarkeit; konkrete Änderungen oder begründete Disposition erforderlich. |
| `VULNERABILITY` | 17 | Sicherheitsklassifikation des Scanners; keine pauschale Bestätigung von 17 erreichbaren Schwachstellen. |
| `BUG` | 1 | Zu prüfender Zuverlässigkeitshinweis; die Bewertung hängt vom konkreten Verhalten ab. |
| Gesamt | **79** | Ungelöste Kennungen zum angegebenen Abrufzeitpunkt. |

Die Sicherheitsklassifikation umfasst 14 Meldungen zu expliziten
Operator-Dateipfaden (`pythonsecurity:S8707`), eine TLS-Meldung
(`python:S4830`) sowie zwei bewusste Verwendungen: die öffentliche Bindung des
separaten Hosted-Launchers hinter Render (`python:S8392`) und den gesetzten
Zufalls-Seed für reproduzierbare Versuchsreihen (`python:S2245`). Die bisherige
Datenflussprüfung fand in den gemeldeten Pfaden keinen vom Browser, Modell oder
ZIP-Import erreichbaren Durchbruch der vorgesehenen Dateigrenzen. Die
TLS-Prüfung verwendet `ssl.create_default_context()` mit Zertifikats- und
Hostnamenprüfung; der Versuchs-Seed erzeugt keine Zugangscodes. Das sind
kontextbezogene Bewertungen mit begrenztem Geltungsbereich, keine Freistellung
aller Datei-, Netzwerk- oder Zufallsverwendungen.

Der eine `BUG`-Hinweis (`python:S2201`) betrifft einen absichtlich nicht weiter
verwendeten Decode-Rückgabewert: Der Aufruf validiert UTF-8, indem ungültige
Bytes eine Ausnahme auslösen. Eine unreflektierte Entfernung dieser Zeile
würde die Prüfung beseitigen. Die früheren Einzelbewertungen und ihre Grenzen
stehen in der [Sonar-Triage](sonar-triage/README.md); deren historische
Gesamtzahlen sind nicht der aktuelle Snapshot.

Für weitere Änderungen gelten folgende Schwerpunkte:

- **Komplexität:** 23 Meldungen zu `S3776` (22 Python, eine TypeScript) betreffen
  größere Funktionen. Sie werden nach fachlichen Verantwortlichkeiten
  aufgeteilt und gegen bisheriges Verhalten geprüft. Ein großer pauschaler
  Umbau des Versuchskerns würde Risiken für Laufbelege, Abbruchverhalten und
  Vergleichbarkeit schaffen und gehört in eigene, gezielte Änderungen.
- **API-Verträge:** Die elf verbleibenden `python:S8415`-Hinweise wurden gegen
  die tatsächlich erzeugten OpenAPI-Responses des exakten Commits geprüft.
  Die unabhängige Prüfung erfasste lokal und gehostet jeweils 22 Operationen:
  alle enthielten die vorgesehenen 400-/404-Antworten mit `APIError`, beide
  abgeschlossenen Kampagnenzugriffe zusätzlich 409 mit `APIError`. Sechs
  vorhandene einschlägige Tests bestanden. Maßgeblich ist der
  wirkliche API-Vertrag, nicht allein die statische Erkennung einer
  Dekorator-Schreibweise.
- **Bewusste Zeichen- und Identitätsregeln:** Die Zeichenklasse `[0-9]` in der
  Hosted-Origin-Prüfung bleibt auf ASCII beschränkt. Ein schematischer Wechsel
  zu `\d` würde in Python zusätzlich Unicode-Ziffern akzeptieren. Auch
  stabile Identitäten in Oberflächenlisten und vorhandene
  Kompatibilitätsbehandlungen müssen anhand ihres konkreten Zwecks geprüft
  werden, bevor ein Scannerhinweis durch eine Verhaltensänderung verschwindet.
- **Kleine Wartbarkeitskorrekturen:** Die zweite Runde bearbeitet ausgewählte
  Darstellungs-, Python- und Workflow-Hinweise getrennt von diesen größeren
  Entscheidungen. Ihre lokale Prüfung ist unten dokumentiert. Der aktuelle
  PR-Head, gesperrte CI und eine neue Inventur müssen den späteren
  Veröffentlichungserfolg und die tatsächliche Befundzahl nachweisen.

## Lokale Folgeprüfung

Die zweite Runde wurde auf `codex/quality-follow-up` implementiert und
unabhängig technisch geprüft; diese Gegenprüfung fand keine blockierenden
Befunde. Sie umfasst weitere gezielte Wartbarkeitskorrekturen und
Regressionstests, keine pauschale Unterdrückung der verbleibenden Regeln.

Unter Linux wurden anschließend lokal ausgeführt:

- Python-Suite mit 306 Testfällen, erfolgreich mit einem ausschließlich unter
  Windows ausführbaren übersprungenen Test;
- 48 React-Tests und erfolgreicher TypeScript-/Vite-Produktionsbuild;
- vollständiger Entwicklungskatalog mit 96 Mock-Läufen sowie Archivexport und
  Wiederherstellung.

**Abhängigkeitsgrenze:** Die lokale Python-Prüfung dieser Folgeänderung verwendete
`pypdf` 6.21.2. Das Repository-Lockfile verlangt seit PR #19 dagegen 6.21.4.
Damit ist dieser lokale Lauf kein Nachweis für die vollständige gesperrte
Abhängigkeitskombination. Vor dem Merge müssen die CI-Läufe des endgültigen
PR-Heads mit dem Lockfile abgeschlossen und geprüft sein. Die weiter oben
belegten erfolgreichen CI-/Deployment-Ergebnisse von `9027b98` gelten nur für
diesen früheren Commit und werden nicht auf die Folgeänderung übertragen.

Für die zweite Runde werden hier weder eine noch unbekannte PR-Nummer noch ein
bereits erfolgreicher Merge, eine Veröffentlichung oder eine neue Sonar-Restzahl
behauptet. Diese Nachweise sind nach ihrem tatsächlichen Abschluss zu ergänzen.

## Noch offene Betriebsarbeit

Der persönliche Zugangscode wurde in dieser Runde **nicht rotiert**. Eine neue
Disk wurde **nicht gebucht oder eingehängt**, `persistent` nicht als erledigt
behauptet und das separate **GitHub-Wiki noch nicht veröffentlicht**. Die
vorbereiteten Anleitungen beziehungsweise Wiki-Dateien ersetzen diese
konkreten Anbieteränderungen nicht.

PR #19 aktualisiert die PDF-Abhängigkeit. Die vom Nutzer genannten sieben
Dependabot-Alerts konnten über den verfügbaren Connector nicht einzeln
abgerufen werden. Daher wird weder ihre vollständige Zuordnung zu `pypdf`
noch ein aktueller Alertbestand von null behauptet. Die Zuordnung und der
Status nach dem Update bleiben in GitHubs Sicherheitsübersicht zu prüfen.

Die Änderungen wurden mit ChatGPT/Codex und getrennten technischen Prüfungen
erarbeitet. Menschliche Autorenabnahme, unabhängige wissenschaftliche
Bewertungen, bestätigte äußere Isolation und ein separat freigegebener echter
API-Pilot bleiben eigene Arbeitsschritte. Es wurden keine empirischen
LLM-Ergebnisse oder menschlichen Freigaben erzeugt.
