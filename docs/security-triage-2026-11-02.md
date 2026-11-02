# Sicherheitsbefunde: Einzelprüfung am 2. November 2026

Diese Prüfung ergänzt die [CodeQL-Triage vom 1. November](codeql-triage-2026-11-01.md).
Sie bezieht sich auf `main` bei
`956e87b12c3d41b859db0972bdcc2019964957a9`, nicht auf spätere Login-Änderungen.
Die neun neu angezeigten CodeQL-Meldungen wurden einzeln anhand ihrer
Detailseiten und vollständigen Datenflüsse geprüft. Die Bewertung wurde
zusätzlich unabhängig am Quellcode gegengeprüft. Beide Prüfungen waren
KI-gestützt; sie ersetzen keine menschliche Autorenabnahme.

## Ergebnis in GitHub

Alle neun Meldungen wurden mit jeweils einer konkreten Begründung als
**False positive** geschlossen. Die anschließende Code-Scanning-Ansicht auf
`main` zeigte **0 offene / 32 geschlossene Meldungen**. Damit wurden neun
Scanner-Fehlalarme eingeordnet, nicht neun nachgewiesene Sicherheitslücken
behoben. CodeQL, seine Regeln und die CI bleiben aktiv; es wurden keine
Dateien, Datenflüsse oder Regeln ausgeschlossen.

Die Meldungen gehören alle zu `py/path-injection`, Schweregrad `High`:

| Alert | Position in `documents.py` | Konkret gemeldete Senke |
|---|---:|---|
| [#25](https://github.com/sxba-04/llm-agent-security-lab/security/code-scanning/25) | 168 | Größenprüfung von `document.json` mit `stat()` |
| [#26](https://github.com/sxba-04/llm-agent-security-lab/security/code-scanning/26) | 168 | Größenprüfung von `original.pdf` mit `stat()` |
| [#27](https://github.com/sxba-04/llm-agent-security-lab/security/code-scanning/27) | 168 | Größenprüfung von `extracted.txt` mit `stat()` |
| [#28](https://github.com/sxba-04/llm-agent-security-lab/security/code-scanning/28) | 170 | Lesen von `document.json` |
| [#29](https://github.com/sxba-04/llm-agent-security-lab/security/code-scanning/29) | 175 | Lesen von `original.pdf` |
| [#30](https://github.com/sxba-04/llm-agent-security-lab/security/code-scanning/30) | 176 | Lesen von `extracted.txt` |
| [#31](https://github.com/sxba-04/llm-agent-security-lab/security/code-scanning/31) | 191 | Existenzprüfung von `confirmation.json` |
| [#32](https://github.com/sxba-04/llm-agent-security-lab/security/code-scanning/32) | 192 | Größenprüfung von `confirmation.json` mit `stat()` |
| [#33](https://github.com/sxba-04/llm-agent-security-lab/security/code-scanning/33) | 194 | Lesen von `confirmation.json` |

## Warum diese konkreten Datenflüsse keinen Pfadausbruch erlauben

Jeder angezeigte Trace beginnt beim URL-Parameter `document_id` in
`server.py:470`, Endpunkt `POST /api/documents/{document_id}/confirm`.
Er führt über `confirm_document()` und `load_document()` nach `_managed()`.
Die Speicherwurzel stammt aus `jobs.documents`, nicht aus dem Request.

Vor dem Zusammensetzen eines Dateipfads verlangt `_managed()` einen vollständigen
Treffer auf `doc-[0-9a-f]{32}\Z`. Damit sind Schrägstriche, Backslashes,
Laufwerkspräfixe, Doppelpunkte, Punkte, Prozentsequenzen, Steuerzeichen und
Unicode-Zeichen in dieser Kennung ausgeschlossen. Der akzeptierte Wert ist genau
ein fest geformter Verzeichnisname unter der vertrauenswürdigen Speicherwurzel.
`reject_symlinks()` prüft zusätzlich die Zugehörigkeit zur Wurzel sowie Links
und Windows-Junctions entlang der Vorfahren. `load_document()` prüft vor den
gemeldeten Zugriffen jede der vier festen Dateien nochmals auf solche Links.
Die Namen `original.pdf`, `extracted.txt`, `document.json` und
`confirmation.json` sind Quellcodekonstanten, keine hochgeladenen Dateinamen.

CodeQL zeigt diese Validierung im Datenfluss, behandelt den resultierenden
Pfad aber weiterhin als unkontrolliert. Die Disposition gilt ausschließlich
für die oben aufgeführten Traces und diese Revision. Sie ist keine pauschale
Freigabe anderer Dateioperationen. Ein Angreifer mit gleichzeitigem direktem
Schreibzugriff auf das Hostdateisystem kann weiterhin Dateisystemrennen
verursachen; die Anwendung beansprucht keine Isolation gegenüber einem
kompromittierten Betriebssystemkonto. Diese dokumentierte Grenze macht einen
anderweitig erreichbaren Web-Pfadausbruch nicht akzeptabel.

## Ausgeführte Gegenprüfungen

Auf Linux mit Python **3.12.14** und `pypdf` **6.21.4** wurden ausgeführt:

```bash
uv run --locked --extra web python -m unittest discover -s tests -p test_document_path_boundaries.py -v
uv run --locked --extra web python -m unittest discover -s tests -p test_documents.py -v
```

**4 Pfadgrenzentests und 7 Dokumenttests bestanden, ohne übersprungene Tests.**
Die Pfadtests decken 16 verschiedene ungültige Kennungen, URL-dekodierte
API-Eingaben, Links an jeder Dokumentdatei und einen verlinkten Dokumentordner
ab. Sie prüfen zusätzlich, dass externe Originaldateien unverändert bleiben
und eine reguläre Bestätigung weiterhin funktioniert. Die Dokumenttests
prüfen unter anderem Originalhashes, Bestätigung, manipulierte Belege und
begrenzte PDF-Extraktion ohne geerbte Provider-Zugangsdaten.

Die geprüften Dokumentfunktionen und diese Testdateien waren gegenüber dem
genannten Analyse-Commit unverändert. Im gemeinsamen Arbeitsstand wurde
parallel am optionalen Login gearbeitet; die hier genannten Läufe sind daher
kein vollständiger Regressionstest oder Review des neuen Login-Features.
Ein tatsächlich unter Windows ausgeführter Test wird hier nicht behauptet.

## Abgrenzung zu Dependabot und Sonar

Die GitHub-Dependabot-Ansicht zeigte am selben Tag **0 offene / 7 geschlossene
Vulnerability-Alerts**. Neue Dependabot-Versions-PRs sind davon getrennte
Wartungsaufgaben. Eine Zahl im allgemeinen Security-Navigationssymbol kann
kurzzeitig hinter dem einzelnen Alertbestand zurückbleiben.

Das verifizierte Sonar-Inventar für die oben genannte Revision enthält weiterhin
**59 ungelöste Befunde**, Quality Gate `OK` und **87,4 % Sonar-Gesamtcoverage**
(Analysezeitpunkt `2026-11-02T01:12:32Z`). Diese Zahl beschreibt den aus GitHub
Actions heruntergeladenen Snapshot. Die Sonar-Weboberfläche lieferte in der
verwendeten Browsersitzung einen CloudFront-HTTP-403-Fehler; ein einmaliges
Neuladen änderte daran nichts. Daher wurden in dieser Runde **keine
Sonar-Statusänderungen vorgenommen** und kein späterer Live-Bestand behauptet.
Die bisherigen Einzelbewertungen stehen in der
[Sonar-Triage](sonar-triage/README.md); künftige Statusänderungen brauchen weiterhin
einen nachvollziehbaren Bezug zur konkreten Meldung und Revision.

Es wurden keine echten Modellaufrufe ausgelöst, keine wissenschaftlichen
Bewertungen erzeugt und keine Versuchsbelege verändert.
