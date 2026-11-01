# Qualitäts- und Sicherheitswerkzeuge

Stand der Einrichtung: 1. November 2026. Diese Werkzeuge prüfen Implementierung
und Zusammenarbeit. Sie sind keine empirische Bewertung der LLM-Abwehrmaßnahmen.

## Zuständigkeiten

| Werkzeug | Aufgabe | Grenze |
|---|---|---|
| Offline tests | Python, React, Produktionsbuild, Browser/API und synthetische Serien auf Linux und Windows | Keine echten Modellaufrufe und keine wissenschaftliche Autorenabnahme |
| Coverage | Python-XML/HTML und React-LCOV/HTML aus den Linux-Unit-Tests | Ausgeführte Zeilen/Zweige sind kein Beweis korrekter Assertions |
| SonarQube Cloud | Statische Befunde, Duplikate und nach CI-Aktivierung importierte Coverage, PR-Quality-Gate | Ein grünes New-Code-Gate beseitigt keine Altbefunde |
| CodeQL Default Setup | GitHub-Analyse von Python, JavaScript/TypeScript und Actions | Keine zusätzliche konkurrierende CodeQL-YAML erforderlich |
| Dependabot | Wöchentliche Versions-PRs für uv, npm und Actions; gesonderte Sicherheitsupdates | Kein automatisches Mergen |
| Dependency review | Neu eingeführte bekannte Schwachstellen in Abhängigkeiten prüfen | Erkennt keine unbekannten Schwachstellen; nutzt GitHubs Dependency-Graph |
| Secret Protection | Unterstützte Geheimnismuster erkennen und Pushes blockieren | Kein Nachweis, dass beliebige sensible Daten erkannt werden |
| Codex, Copilot, Gitar | Ergänzende PR-Reviews im bereits verbundenen Setup | Quotenfehler sind nicht bestanden; Befunde benötigen Gegenprüfung |

Codecov wird zunächst nicht zusätzlich angeschlossen: CI-Artefakte und Sonar
decken die gewünschte gemeinsame Coverage-Auswertung ab. Ein weiterer Dienst ist
erst sinnvoll, wenn nach Nutzung dieser Berichte ein konkreter Darstellungsbedarf
bleibt. FastAPI Cloud ist eine alternative Hosting-Plattform, kein erforderlicher
CI-Baustein für den bestehenden Render-Dienst; es wird kein zweites Deployment
angelegt.

## Coverage nachvollziehbar lesen

`Offline tests` erzeugt auf Linux zwei Artefakte für denselben getesteten Stand:

- `python-coverage`: `coverage/python/coverage.xml`, JSON und HTML. Alle Module in
  `src/security_lab` und die Python-Hilfsskripte in `scripts` werden erfasst, auch
  unimportierte. Die Aufnahme von `scripts` ab November verändert den Nenner;
  frühere Quoten nur für Anwendungsmodule sind damit nicht direkt vergleichbar. XML verwendet relative
  Quellpfade; die Messung umfasst Zeilen und Zweige.
- `frontend-coverage`: `frontend/coverage/lcov.info`, Zusammenfassung und HTML.
  Alle produktiven TS/TSX-Dateien werden berücksichtigt; Testdateien,
  Test-Setup und Typdeklarationen sind keine Coverage-Ziele. LCOV verweist auf
  `frontend/src/...` relativ zum Repository.

Die Artefakte bleiben 14 Tage verfügbar. Die GitHub-Job-Zusammenfassung zeigt
Coverage-Werte. Die Windows-Jobs behalten ihre regulären Verhaltens- und
Integrationstests. PDF-/CLI-Unterprozesse und Browser-E2E werden separat geprüft,
aber nicht in die Unit-Coverage aufaddiert. Es gibt zunächst keine willkürliche
zusätzliche Mindestquote; konkrete Lücken und relevante Fehlerpfade sind die
Grundlage weiterer Tests. Sonars eigenes Quality Gate bleibt wirksam, sobald die
CI-Analyse aktiviert ist.

Sonar fasst Python- und Frontend-Messungen nach seiner eigenen Metrik zusammen.
Diese Gesamtquote nicht mit einzelnen Python-Zeilen- oder Zweigquoten gleichsetzen.
Für die Einzelprüfung der bestehenden Befunde gibt es eine
[lesende, versionierte Inventur](sonar-inventory.md) mit eigenem manuellen Workflow.

Lokale Ausgangsmessung am 30.10.2026: Python 271 Tests, davon ein Windows-Test unter
Linux übersprungen; Zeilen 3080/3466 (88,86 %), Zweige 1084/1344 (80,65 %).
Coverage.py kombiniert beide Dimensionen zu 86,57 %. React: 31 bestandene Tests,
Zeilen 394/444 (88,73 %), Zweige 651/905 (71,93 %). Das sind lokale Messwerte des
Einrichtungsstands; verbindlich für einen PR sind dessen aktuelle CI-Artefakte.

## Sonar sicher auf CI-Analyse umstellen

Das Projekt `sxba-04_llm-agent-security-lab` gehört zur Organisation `sxba-04`.
GitHub enthält das Repository-Secret `SONAR_TOKEN` und die Repository-Variablen
`SONAR_ORGANIZATION=sxba-04` sowie `SONAR_CI_ENABLED=true`. Die Werte stehen unter
**Settings → Secrets and variables → Actions → Variables**; der Token gehört
stattdessen auf den Reiter **Secrets**. GitHub zeigt gespeicherte Secret-Werte
nicht wieder an. Die GitHub-Verbindung gibt einem Werkzeug Berechtigungen, aber
keinen Zugriff auf das Passwort oder den Inhalt bereits gespeicherter Secrets.

Die Analyse bleibt automatisch: `Offline tests` startet bei Änderungen an `main`
und bei Pull Requests und ruft nach den Tests den gemeinsamen Sonar-Workflow auf.
Sonars separat benannte **Automatic Analysis** läuft ohne unsere Tests und kann
keine Coverage importieren. Deshalb wird sie durch die automatische CI-Analyse
ersetzt. Beide Analysearten dürfen nicht parallel für dieses Projekt laufen.

Es wird kein zusätzlicher Beispiel-Workflow `build.yml` aus dem Onboarding
benötigt. Er würde erneut ohne unsere Coverage, Quell-/Testzuordnung und
PR-Schutzbedingungen scannen. Die verbindliche Konfiguration bleibt in
`tests.yml`, `sonar.yml` und `.github/sonar-project.properties`.

Für eine erneute Einrichtung oder einen späteren Tokenwechsel gilt:

1. In Sonar unter Projekt → Administration → Analysis Method den GitHub-Actions-
   Einrichtungsdialog öffnen und den **Organization Key `sxba-04`** prüfen.
   Als GitHub-Repository-Variable `SONAR_ORGANIZATION` speichern. Nicht den
   Anzeigenamen oder den Projektschlüssel einsetzen.
2. Einen Sonar-Token mit Analyserecht und sinnvoller Ablaufzeit erstellen und
   direkt unter GitHub → Settings → Secrets and variables → Actions als
   **Repository Secret `SONAR_TOKEN`** hinterlegen. Nicht in Chat, Quellcode,
   Repository-Variablen oder Screenshots kopieren. Free verwendet persönliche
   Tokens; das ist kein Anlass für ein kostenpflichtiges Upgrade.
3. Erst wenn Token und Organisationsschlüssel bereitstehen, in Sonar
   **Automatic Analysis ausschalten** und die GitHub-Repository-Variable
   `SONAR_CI_ENABLED` auf `true` setzen. Automatische und CI-Analyse dürfen nicht
   gleichzeitig laufen. Eine kurze Unterbrechung während dieser Umstellung ist
   zu erwarten; in dieser Zeit keine ungeprüften PRs mergen.
4. `Offline tests` auf `main` manuell starten. Die Sonar-Jobs warten auf sämtliche
   Python-/Frontend-Matrixjobs, laden ausschließlich Coverage-Artefakte dieses
   Workflow-Laufs und analysieren mit vollständiger Git-Historie. Prüfen, dass
   XML und LCOV importiert werden, Commit und Coverage in Sonar stimmen und das
   Quality Gate abgeschlossen ist. Anschließend einen aktuellen PR prüfen.

Die Konfiguration liegt in `.github/sonar-project.properties` und wird dem
Scanner explizit übergeben. Der Scanner setzt
`sonar.scanner.autoconfig.enabled=false`, damit die separat angebotene
**Automatic configuration (Beta)** unsere ausdrückliche Quell-/Testzuordnung
nicht ignoriert. Dieser Schalter ist unabhängig von **Automatic Analysis** und
ändert keine Coverage-Berichtspfade. Die Konfigurationsdatei liegt weiterhin
außerhalb des Repository-Roots und wird ausdrücklich ausgewählt. Der Job
`Sonar integration status` erklärt bei deaktivierter CI-Analyse den Grund.
`Sonar analysis and quality gate` wird dann übersprungen. Ein solcher Skip ist
kein bestandenes Quality Gate. Ist CI-Analyse aktiviert, führen fehlende
Organisation, fehlender Token oder fehlende Berichte zu einem Fehler.

Fork- und Dependabot-PRs bekommen keinen Sonar-Token. Ihre normalen Tests und
Coverage-Berichte laufen weiter; die Sonar-CI-Analyse wird ausdrücklich
übersprungen. Es gibt keinen `pull_request_target`-Workflow, der fremden PR-Code
mit Geheimnissen ausführt. Nach dem Merge wird `main` analysiert. Diese Grenze
beachten, bevor Sonar als ausnahmslos erforderlicher Merge-Check eingestellt wird.

## Befunde und Repository-Schutz

Beim Kontocheck waren Dependency Graph, automatische Dependency Submission,
Dependabot-Warnungen, Malware-Warnungen, Sicherheitsupdates, gruppierte
Sicherheitsupdates, CodeQL Default Setup, Secret Protection, Push Protection
und private Sicherheitsmeldungen eingeschaltet. Agentic Autofix, das zusätzliche
KI-Credits verbraucht, war ausgeschaltet und bleibt unverändert.

Das aktive Ruleset `Protect main` verlangt PRs, aufgelöste Review-Threads und
aktuelle erfolgreiche Python-/Frontend-Jobs für Linux und Windows. Es verhindert
Löschen und Force-Pushes, ohne Bypass. Der Schutz wird nicht abgeschwächt.

Der erste Sonar-Screenshot zeigt 39 Security-, 5 Reliability- und 189
Maintainability-Befunde im Gesamtbestand. Diese Zahlen wurden nicht als
validierte Schwachstellen übernommen. Ein bestandener PR-Check bei reinen
Issue-Vorlagen sagt lediglich etwas über dessen neue Änderungen aus. Die
Altbefunde müssen anhand Regel, Datei, erreichbarem Datenfluss und tatsächlicher
Auswirkung gegen [SECURITY.md](../SECURITY.md) geprüft werden. Kein pauschales
`NOSONAR`, keine Blanket-Exclusions und kein Schließen als False Positive ohne
Begründung. Absichtlich fehlende synthetische B/F-Policy ist von einem Fehler der
äußeren Isolation zu unterscheiden.

GitHubs Code-Scanning-Übersicht zeigte bei dieser Kontrolle zusätzlich 23 offene
CodeQL-Meldungen auf `main`: 22 zu Pfadausdrücken und eine zur TLS-Konfiguration
des HTTPS-Testservers. Alle waren als High eingestuft. Das ist eine
Scanner-Inventur, keine Bestätigung von 23 ausnutzbaren Schwachstellen. Die
22 Pfadmeldungen wurden am 01.11.2026 einzeln anhand ihrer Datenflüsse geprüft
und mit konkreter Begründung als False Positive abgeschlossen. Die TLS-Meldung
bleibt bis zur verifizierten ausdrücklichen Mindestversion im Testserver offen.
Die Analyseregeln bleiben aktiv; es gibt keine pauschale Unterdrückung.

Sinnvolle nächste Schritte sind die priorisierte Befundprüfung, gezielte Tests
für bislang ungetestete Fehlerpfade und die gemeinsame fachliche Abnahme von
Fällen und Bewertungsrubrik. Erst vor echten Modellversuchen folgen Nachweis der
äußeren Isolation und gesonderter API-Pilot. Langlebige Studienbelege benötigen
weiterhin eine gesonderte Speicherentscheidung; kostenlose Hosting-Dienste werden
nicht durch Keep-alive-Pings künstlich wachgehalten.

## Offizielle Referenzen

- [Sonar mit GitHub Actions](https://docs.sonarsource.com/sonarqube-cloud/analyzing-source-code/ci-based-analysis/github-actions-for-sonarcloud)
- [Python-Coverage und Wechsel von Automatic Analysis](https://docs.sonarsource.com/sonarqube-cloud/analyzing-source-code/test-coverage/python-test-coverage)
- [JavaScript-/TypeScript-Coverage](https://docs.sonarsource.com/sonarqube-cloud/analyzing-source-code/test-coverage/javascript-typescript-test-coverage)
- [Dependabot-Konfiguration](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)
- [uv und Dependabot](https://docs.astral.sh/uv/guides/integration/dependabot/)
