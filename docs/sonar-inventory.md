# Sonar-Befunde einzeln prüfen

Nach einer erfolgreichen Sonar-Analyse eines Pushs auf `main` legt die reguläre
CI zusätzlich automatisch das unten beschriebene Befundinventar als Artefakt ab.
Es verwendet denselben lesenden, begrenzten Export wie der manuelle Workflow.
Für konfigurierte PR-Läufe aus demselben Repository (außer Dependabot) wird
zusätzlich ein PR-Inventar erzeugt. Es wird auch nach einem fehlgeschlagenen
Quality Gate hochgeladen, sofern der Scanner bereits einen Bericht eingereicht
hat und die lesende Inventur vollständig gelingt. Das fehlgeschlagene Gate
bleibt fehlgeschlagen. Ohne Scanner-Einreichungsbeleg, bei abgebrochenem Job,
Fork-/Dependabot-PR oder fehlender Konfiguration wird kein PR-Inventar behauptet.

Unter **Actions → Read-only Sonar issue inventory → Run workflow → main** lässt
sich der aktuelle offene Befundbestand abholen. Beide optionalen Eingaben leer
lassen für `main`; für eine PR-Inventur `pull_request` und die vollständige
`expected_revision` angeben. Die Auswahl verändert den abgefragten Sonar-Stand,
nicht den ausgeführten Code: der manuelle Workflow bleibt auf `main` begrenzt.
Er läuft unabhängig von der vollständigen Testsuite. Der Workflow analysiert keinen
Code neu und ändert keine Einstellungen, Befunde oder Quality Gates. Er nutzt
das bereits hinterlegte GitHub-Actions-Secret `SONAR_TOKEN` ausschließlich für
GET-Anfragen an `https://sonarcloud.io`. Der Token muss Leserechte für das Projekt
haben; fehlt die Berechtigung, schlägt der Lauf ausdrücklich fehl.

Das Artefakt `sonar-main-inventory` bleibt 14 Tage verfügbar und enthält
`sonar-main.json` für `sxba-04_llm-agent-security-lab`, Branch `main`:

- alle vom API-Filter `resolved=false` erfassten Befunde, vollständig paginiert;
- Regelkennung, Datei, Zeile, Typ/Schweregrad/Status und verfügbare Datenflusspositionen;
- Analysekennung, Analysedatum und vollständigen Git-Commit;
- Coverage-/Duplikationsmesswerte und Quality-Gate-Bedingungen.

Autoren, Bearbeiter, E-Mail-Felder, Kommentare und Quelltexte werden nicht
exportiert. Auch Freitextdiagnosen (`message`) und Meldungen an Datenflusspositionen
(`msg`) werden vollständig ausgelassen: Sie können vertrauliche Quelltextliterale
oder personenbezogene Angaben zitieren. Regelkennungen und Fundstellen erlauben
die Prüfung am angegebenen Quellcode-Commit; zusätzliche Diagnoseinformationen
bleiben in Sonar. Fehlende Messwerte erscheinen als `missing_metrics`, nicht als null
Prozent. Das Ergebnis ist eine Momentaufnahme für die anschließende Bewertung
gegen [SECURITY.md](../SECURITY.md), kein Nachweis bestätigter Schwachstellen.
Ein bestandenes Quality Gate bedeutet nicht, dass keine Altbefunde bestehen.

Der manuelle Workflow läuft ausschließlich auf `main`. Die reguläre Analyse
ergänzt den oben begrenzten PR-Export; URL und Projekt sind weiterhin fest
vorgegeben. Umgeleitete HTTP-Anfragen werden abgebrochen;
HTTP-Fehler protokollieren weder Antwortkörper noch Zugangsdaten. Fehlende Seiten,
wechselnde Gesamtzahlen, doppelte Befundkennungen, unerwartete Datenstrukturen
oder mehr als 10.000 Befunde verhindern die Veröffentlichung eines Artefakts.
Die letzte Analyse wird vor und nach der Erhebung verglichen; bei einem Wechsel
ist ein erneuter Lauf nötig. Gleichzeitige manuelle Befundänderungen können ohne
neue Analyse auftreten: Die API bietet hier keinen unveränderlichen Snapshot.

Die JSON-Datei bezieht sich auf den enthaltenen Analyse-Commit, der vom aktuellen
`main`-Commit abweichen kann. Vor einer Korrektur oder abschließenden Bewertung
diesen Stand mit dem Quellcode vergleichen und nach einer neuen Analyse eine
neue Inventur erstellen. Geschlossene Befunde und Modellversuche
sind nicht Teil dieser Exporte. Die Anwendung und ihr Render-Workspace werden
dabei nicht aufgerufen.

## PR-Inventar bei fehlgeschlagenem Gate

Das separate Artefakt **sonar-pr-inventory** enthält `sonar-pr.json` und bleibt
ebenfalls 14 Tage verfügbar. Es fragt Befunde, Messwerte und Gate ausdrücklich
mit `pullRequest=NUMMER` ab; ein Branch-Parameter wird dabei nicht gesendet.
Der PR-Schlüssel, das letzte Analysedatum und der gemeldete Gate-Status werden
über `project_pull_requests/list` vor und nach der Erhebung verglichen.
`project_analyses/search` wird für PRs nicht verwendet. Fehlende oder wechselnde
PR-Analysen verhindern ein als vollständig ausgewiesenes Inventar.

Die Aufrufsyntax für denselben lesenden Export lautet:

```powershell
python scripts/sonar_inventory.py --pull-request 30 --expected-revision VOLLSTAENDIGE_GIT_SHA
```

Die PR-Nummer muss eine positive ganze Zahl sein, die erwartete Revision eine
vollständige hexadezimale Git-SHA (40 oder 64 Zeichen). `SONAR_TOKEN` bleibt
ausschließlich eine Umgebungsvariable. Ohne PR-Optionen bleibt der bisherige
`main`-Export unverändert auswählbar. Eine zusätzlich für `main` übergebene
erwartete Revision muss zur serverseitig gelieferten Analyse-Revision passen.

In CI bezeichnet `expected_revision` den PR-Head aus dem Event; der Scanner erhält
denselben Wert explizit als `sonar.scm.revision`. Der ausgecheckte und getestete
Quellbaum kann der GitHub-PR-Merge-Commit sein. **Die PR-Listing-API liefert keine
Git-Revision:** Das Inventar kennzeichnet deshalb `server_revision_verified=false`.
Die erwartete SHA ist Scanjob-Kontext und kein erfundener serverseitiger
Revisionsnachweis. Nach früher abgebrochener Analyse kann der gelesene PR-Stand
noch einer älteren Einreichung entsprechen; Analysedatum und Scanjob gemeinsam
prüfen, bevor Befunde dem aktuellen Code zugerechnet werden.

CI übergibt außerdem `--scanner-report .scannerwork/report-task.txt`. Dieser
lokale Einreichungsbeleg wird auf Größe, festen Host und Projekt geprüft; nur
die validierte CE-Task-ID gelangt in das Inventar. Der Task wird nicht zusätzlich
serverseitig abgefragt. Die vollständige Datei, Dashboard-/Task-URLs und mögliche
unbekannte Felder werden nicht hochgeladen. Ein Beleg beweist die Einreichung,
nicht allein eine erfolgreich abgeschlossene Analyse oder deren Commit.

Für PRs werden zusätzlich New-Code-Coverage und Duplikationswerte angefragt.
API-`period`-Werte bleiben unter `period_values` von allgemeinen `values` getrennt.
Auch die von Sonar verwendete `periods`-Liste wird unterstützt: alle gelieferten
Indizes und Werte bleiben unter `periods` erhalten. Nur ein einzelner eindeutiger
Listeneintrag wird zusätzlich in `period_values` abgebildet; mehrere Perioden
werden weder zusammengelegt noch willkürlich ausgewählt. `bestValue` wird
nicht als numerischer Wert interpretiert. Nicht gelieferte Größen erscheinen
als `missing_metrics`; gelieferte Metriken ohne Wert, mit `null` oder leerem
Wert stehen unter `unavailable_metrics`. Dies erzeugt keine Null-Prozent-Werte
und verwirft weder die Befunde noch ein fehlgeschlagenes Gate. Unzulässige
Datentypen, doppelte Periodenindizes oder mehr als zehn Perioden bleiben Fehler.
Issue-IDs, Regeln und Positionen bleiben verfügbar, während Meldungstexte,
Autoren, Kommentare, PR-Titel und Quellcode weiterhin ausgelassen werden.

Offizielle API-Dokumentation: [Web API und Bearer-Authentifizierung](https://docs.sonarsource.com/sonarqube-cloud/appendices/web-api),
[Issues](https://sonarcloud.io/web_api/api/issues/search),
[Measures](https://sonarcloud.io/web_api/api/measures/component),
[Quality Gate](https://sonarcloud.io/web_api/api/qualitygates/project_status),
[Projektanalysen](https://sonarcloud.io/web_api/api/project_analyses/search),
[PR-Analysen](https://sonarcloud.io/web_api/api/project_pull_requests/list).
