# Sonar-Befunde einzeln prüfen

Nach einer erfolgreichen Sonar-Analyse eines Pushs auf `main` legt die reguläre
CI zusätzlich automatisch das unten beschriebene Befundinventar als Artefakt ab.
Es verwendet denselben lesenden, begrenzten Export wie der manuelle Workflow.
PR-Läufe führen diesen Export nicht aus. Bei fehlgeschlagener Analyse oder
fehlgeschlagenem Quality Gate bleibt der manuelle Workflow zur Diagnose verfügbar.

Unter **Actions → Read-only Sonar issue inventory → Run workflow → main** lässt
sich der aktuelle offene Befundbestand abholen. Der Workflow analysiert keinen
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

Der Workflow läuft ausschließlich auf `main`, ohne PR-Trigger oder frei
wählbare URL-/Projektparameter. Umgeleitete HTTP-Anfragen werden abgebrochen;
HTTP-Fehler protokollieren weder Antwortkörper noch Zugangsdaten. Fehlende Seiten,
wechselnde Gesamtzahlen, doppelte Befundkennungen, unerwartete Datenstrukturen
oder mehr als 10.000 Befunde verhindern die Veröffentlichung eines Artefakts.
Die letzte Analyse wird vor und nach der Erhebung verglichen; bei einem Wechsel
ist ein erneuter Lauf nötig. Gleichzeitige manuelle Befundänderungen können ohne
neue Analyse auftreten: Die API bietet hier keinen unveränderlichen Snapshot.

Die JSON-Datei bezieht sich auf den enthaltenen Analyse-Commit, der vom aktuellen
`main`-Commit abweichen kann. Vor einer Korrektur oder abschließenden Bewertung
diesen Stand mit dem Quellcode vergleichen und nach einer neuen Analyse eine
neue Inventur erstellen. Geschlossene Befunde, PR-Analysen und Modellversuche
sind nicht Teil dieses Exports. Die Anwendung und ihr Render-Workspace werden
dabei nicht aufgerufen.

Offizielle API-Dokumentation: [Web API und Bearer-Authentifizierung](https://docs.sonarsource.com/sonarqube-cloud/appendices/web-api),
[Issues](https://sonarcloud.io/web_api/api/issues/search),
[Measures](https://sonarcloud.io/web_api/api/measures/component),
[Quality Gate](https://sonarcloud.io/web_api/api/qualitygates/project_status),
[Projektanalysen](https://sonarcloud.io/web_api/api/project_analyses/search).
