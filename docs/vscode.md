# VS Code und gemeinsame Aufgaben

Die Einträge **Labor: …** unter **Terminal → Aufgabe ausführen** stammen aus der versionierten [.vscode/tasks.json](../.vscode/tasks.json). Sie sind Befehlsabkürzungen für dieselben Python- und npm-Befehle, die sich im Terminal ausführen lassen. Nach einem aktuellen Clone oder Pull stehen sie allen zur Verfügung, sobald der Repository-Ordner in VS Code geöffnet ist. Eine Python-Erweiterung ist für diese Aufgaben nicht erforderlich.

## Voraussetzungen

Git, uv und Node.js müssen separat über einen auf dem Rechner erlaubten Weg installiert werden. Die Aufgaben installieren diese Werkzeuge nicht. Benötigt wird **Node.js 24 ab Version 24.15.0, kleiner als 25**, einschließlich npm; uv kann die in `.python-version` festgelegte Python-Version bereitstellen. Die [Windows-Anleitung](setup-windows.md) beschreibt die Einrichtung.

In einem neuen VS-Code-Terminal prüfen:

```powershell
git --version
uv --version
node --version
npm.cmd --version
```

Alle Programme müssen über den `PATH` erreichbar sein. Nach einer Werkzeuginstallation kann ein Neustart von VS Code nötig sein. Bei einem Fehler zuerst dessen Ursache beheben. Unter Linux und macOS wird `npm` anstelle von `npm.cmd` verwendet; die gemeinsamen Aufgaben wählen den passenden Befehl. Unter Windows ist keine Änderung der PowerShell-Ausführungsrichtlinie nötig.

## Erster Start

1. Den Ordner `llm-agent-security-lab` in VS Code öffnen.
2. **Terminal → Aufgabe ausführen → Labor: Gesamtinstallation** wählen und den erfolgreichen Abschluss abwarten. Sie führt Python-Synchronisierung, `npm ci` und Frontend-Build nacheinander aus.
3. **Labor: Oberflaeche starten** ausführen. Die Aufgabe baut das Frontend und startet anschließend den lokalen Python-Dienst.
4. Im Browser `http://127.0.0.1:8765` öffnen. Das Server-Terminal bleibt während der Nutzung offen; Strg+C beendet den Dienst.

Schlägt ein Schritt fehl, die Ursache im Task-Terminal beheben und den Schritt wiederholen, bevor es weitergeht. Läuft bereits ein Laborserver auf Port 8765, diesen zuerst beenden. Die Oberfläche führt ausschließlich Mock-Versuche aus und benötigt keinen API-Schlüssel.

## Verfügbare Aufgaben

| Aufgabe | Zweck |
|---|---|
| Labor: Gesamtinstallation | Python-Umgebung, Frontend-Pakete und Build nacheinander vorbereiten |
| Labor: Umgebung synchronisieren | `uv sync --locked --extra web --group dev` ausführen |
| Labor: Frontend installieren | Frontend-Pakete anhand der Lockdatei mit `npm ci` installieren |
| Labor: Frontend bauen | TypeScript prüfen und Produktionsbuild erstellen |
| Labor: Oberflaeche starten | Frontend bauen und Werkbank auf Port 8765 starten |
| Labor: Demo (24 Mock-Laeufe) | Kleine technische CLI-Demo ausführen |
| Labor: Entwicklungskatalog (96 Mock-Laeufe) | Alle Entwicklungspaare einmal in allen Bedingungen ausführen |
| Labor: Fallkatalog validieren | Fallstruktur prüfen |
| Labor: Alle Tests | Die vollständige Python-Testsuite ausführen |
| Labor: Frontend Tests | React-Tests ausführen |
| Labor: Browser installieren | Den von Playwright benötigten Chromium-Testbrowser herunterladen |
| Labor: Browsertests | Frontend bauen und Browser-/API-Integration prüfen |
| Labor: Browserbericht oeffnen | Den vorhandenen Playwright-Bericht auf Port 9323 anzeigen |

Für Browsertests nach der Gesamtinstallation einmal **Labor: Browser installieren** ausführen; nach einem Playwright-Update gegebenenfalls wiederholen. Vor **Labor: Browsertests** den normalen Laborserver auf Port 8765 stoppen. Die Tests starten ihren eigenen Dienst mit Daten unter `runs/browser-ci/`. Für die normale Bedienung der Oberfläche genügt der vorhandene Browser.

Unter Linux können zusätzlich Systembibliotheken für Chromium erforderlich sein. Diese nach den Vorgaben des Rechners bereitstellen; Playwright bietet dafür im Ordner `frontend` den Befehl `npm run browsers:install -- --with-deps` an. Die normale Browseraufgabe installiert keine Betriebssystempakete.

**Labor: Alle Tests** ist der bestehende Name der Python-Prüfung; Frontend- und Browsertests werden über ihre eigenen Aufgaben gestartet. Testberichte und Mock-Ergebnisse sind technische Kontrollen, keine empirischen Ergebnisse zur Angreifbarkeit eines LLM.

## Nach einem Update

Den Server beenden und bei sauberem Arbeitsstand im Repository-Verzeichnis `git pull --ff-only` ausführen. Danach **Labor: Gesamtinstallation** und anschließend **Labor: Oberflaeche starten** ausführen. Die Aufgaben und Lockdateien werden durch Git aktualisiert; Projektumgebung, Pakete und Laufdaten bleiben lokal.

## Persönliche Einstellungen

Nur `.vscode/tasks.json` wird gemeinsam verteilt. `.vscode/settings.json` und `.vscode/launch.json` bleiben ignoriert und können lokal Interpreter, Debugger und persönliche Einstellungen enthalten. Die gemeinsamen Aufgaben enthalten keine Firmenproxywerte oder absoluten Rechnerpfade.

Falls lokale Programme oder der Firmenproxy zusätzliche Terminal-Umgebungsvariablen benötigen, werden sie unter `terminal.integrated.env.windows` eingerichtet:

- Bei direkt geöffnetem Repository-Ordner in der lokalen `.vscode/settings.json`.
- Bei einem gespeicherten Arbeitsbereich in dessen persönlicher `.code-workspace`-Datei außerhalb des Repositorys, unter `settings`. Diese Terminal-Einstellung wird dort nicht aus den Ordnereinstellungen übernommen.

Eine persönliche `PATH`-Erweiterung muss den vorhandenen Wert über `${env:PATH}` erhalten. Proxy, Zertifikate und mögliche Downloadpfade werden nach den Vorgaben des jeweiligen Rechners gesetzt; Zugangsdaten gehören nicht in diese gemeinsame Taskdatei. Nach einer Änderung alte Terminals mit dem Papierkorb beenden und neue öffnen. Bereits laufende Terminals übernehmen die Umgebung nicht nachträglich.

Sind die Aufgaben nicht sichtbar, prüfen, ob der aktuelle Repository-Ordner geöffnet ist und `.vscode/tasks.json` aus dem aktuellen Branch vorhanden ist. Meldet ein Task einen unbekannten Befehl, zuerst die Werkzeuginstallation und den `PATH` prüfen. Hinweise zur fachlichen Bedienung stehen in [Laboroberfläche](workbench.md).
