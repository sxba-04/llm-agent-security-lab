# Veröffentlichung und Rückkehr zum letzten geprüften Stand

Diese Anleitung gilt für die bestehende Pages-Oberfläche und den einzelnen
Render-Dienst `srv-dbhmac67bikc73f0cvug` mit persistenter Disk. Sie beschreibt
einen Ablauf, keinen bereits durchgeführten Rollback-Test.

## Vor der Veröffentlichung

1. Den endgültigen PR-Head, bestandene Pflichtprüfungen, abgeschlossene Code- und
   Security-Reviews sowie die unabhängige technische Gegenprüfung festhalten.
2. In **Versuche** prüfen, dass keine Kampagne läuft, und einen PDF-Import
   abschließen lassen. Keine neuen Arbeiten während der Bereitstellung starten.
3. Den Forschungsbestand [extern sichern und getrennt wiederherstellen](workspace-backup.md).
   Archivhash und den tatsächlich laufenden Backend-Commit notieren.
4. Den PR regulär mergen. Pages- und Render-Bereitstellung getrennt beobachten;
   ein grüner PR ist noch kein Nachweis eines erfolgreichen Deployments.
5. Auf Render den erfolgreichen Deploy und dessen Commit prüfen. Der bestehende
   Modus **After CI Checks Pass** bleibt aktiv; keinen zweiten manuellen Deploy
   starten, während die automatische Bereitstellung bereits läuft.

## Nach der Veröffentlichung

- `/healthz` muss HTTP 200 liefern. Ohne Anmeldung bleiben geschützte API-Routen
  gesperrt. Die GitHub-Anmeldung erneut prüfen; Sitzungen liegen im Prozessspeicher.
- In der angemeldeten Werkbank müssen die bisherigen Kampagnen und Quellen
  erhalten sein. Einen vorhandenen Archivexport erneut prüfen und seine
  Originaldateien mit der Vorab-Sicherung vergleichen.
- Theme, Fallansicht, begrenzten Mock-Lauf, Vergleich, Download und Sitzungsmenü
  prüfen. Neue technische Kampagnen als solche benennen; keine menschlichen
  Bewertungen oder wissenschaftlichen Quellenfreigaben für die Abnahme erfinden.
- In Render CPU/RAM und Ereignisse beobachten. Ein erfolgreicher kleiner Mock
  belegt keine ausreichende Kapazität für jede PDF-Größe oder Hauptmessung.
- Beim ersten Luna-Rollout angemeldet die gesperrte Pilotansicht prüfen. Vor einem Rollback oder einer Wiederherstellung nach einem begonnenen Pilotversuch den Piloten deaktivieren. Vor dem nächsten Start Versuchsnachweis, Budgetprotokoll und Anbieternutzung abgleichen: Ein älterer Diskstand kann den Nachweis eines bereits berechneten Aufrufs verlieren.
- Tatsächlich laufenden Commit, Deploy-ID, Zeitpunkt, Prüfergebnisse und
  verbleibende Grenzen im PR dokumentieren.

## Bei einer fehlerhaften Veröffentlichung

Zuerst Belege erhalten und Fehlerumfang bestimmen. Keine Kampagne erneut
ausführen, um einen Speicherfehler zu verdecken. Ein unterbrochener Lauf bleibt
als solcher dokumentiert.

Für eine dringende Rückkehr im Render-Dashboard unter **Deploys** einen zuvor
erfolgreichen, noch verfügbaren Deploy auswählen und **Rollback** bestätigen.
Dabei Startkommando, Healthcheck und Umgebung des Zielstands bewusst prüfen.
Ein Dashboard-Rollback deaktiviert automatische Deployments; ein API-Rollback
tut dies nicht. Die Disk behält ihre aktuellen Daten. Ein Code-Rollback stellt
keine früheren Dateibelege wieder her. Die angehängte Disk bedeutet außerdem,
dass Bereitstellungen eine kurze Unterbrechung verursachen können.

Pages wird dadurch nicht zurückgesetzt. Für einen konsistenten dauerhaften
Rückweg einen neuen Korrektur- oder Revert-PR erstellen, beide Clients gegen
den vorgesehenen API-Vertrag prüfen und den üblichen Review-/CI-Ablauf einhalten.
Keine Branchhistorie zurücksetzen oder Schutzregeln umgehen. Nach der Korrektur
den dokumentierten Auto-Deploy-Modus **After CI Checks Pass** wiederherstellen,
falls der Dashboard-Rollback ihn deaktiviert hat.

Bei beschädigten Daten zuerst die Sicherung in einen neuen lokalen Ordner
wiederherstellen. Keine produktive Disk und keine neueren Originalbewertungen
mit einem älteren Snapshot überschreiben. Datenrettung und Code-Rollback sind
getrennte Entscheidungen.

## Nachweise und Quellen

Die bisherigen kontrollierten Neustarts stehen in [Validierung](validation.md).
Ein echter Anbieter-Rollback wurde für dieses Paket nicht behauptet oder
unnötig gegen den laufenden Dienst ausgeführt.

Anbieterregeln geprüft am 6. November 2026:
[Render Rollbacks](https://render.com/docs/rollbacks),
[Deployments und CI](https://render.com/docs/deploys),
[Healthchecks](https://render.com/docs/health-checks).

KI-Unterstützung: Diese Anleitung wurde mit Codex erstellt und anhand der
vorhandenen Konfiguration und Anbieterunterlagen geprüft.
