# Einrichtung unter Windows

Die Anwendung wird auf jedem Rechner aus demselben Git-Repository gestartet. Jeder Rechner besitzt eine eigene Projektumgebung und lokale Zugangsdaten. Ein gemeinsamer Server oder eine GPU ist für die technischen Tests und den API-Betrieb nicht erforderlich.

## Einrichtung mit uv

Installiere Git und uv über einen auf dem jeweiligen Rechner erlaubten Weg. Die [uv-Dokumentation](https://docs.astral.sh/uv/getting-started/installation/) beschreibt die verfügbaren Installationswege. Für die Oberfläche wird zusätzlich Node.js 24 ab Version 24.15.0, kleiner als 25, einschließlich npm benötigt. Auf einem verwalteten Firmenrechner gelten dessen Installations- und Netzwerkvorgaben.

Nach der Installation VS Code gegebenenfalls neu starten und in einem neuen Terminal `git --version`, `uv --version`, `node --version` und `npm.cmd --version` prüfen. Die Programme müssen über den `PATH` erreichbar sein. Node und npm sind für einen reinen CLI-Lauf nicht erforderlich. Die Befehle einzeln ausführen und bei einem Fehler anhalten:

```powershell
git clone https://github.com/sxba-04/llm-agent-security-lab.git
cd llm-agent-security-lab
uv sync --locked --extra web --group dev
uv run --locked --extra web python -m security_lab --help
uv run --locked --extra web python -m security_lab demo --output runs/demo
uv run --locked --extra web --group dev python -m unittest discover -s tests -v
```

`uv sync --locked --extra web --group dev` verwendet die versionierten Abhängigkeiten und installiert auch die Pakete für Oberfläche und vollständige Python-Tests. Änderungen an der Lockdatei gehören in einen überprüften Commit. Wenn die in `.python-version` festgelegte Python-Version fehlt, kann uv sie herunterladen; auch dieser Download muss durch die lokale Netzwerkkonfiguration zugelassen sein. `--extra web` bei späteren CLI-Aufrufen erhält die installierten Webpakete.

Weder `Activate.ps1` noch das Abschalten von PowerShell-Schutzfunktionen sind für diesen Ablauf erforderlich.

## Alternative mit vorhandenem Python

Der Anwendungskern verwendet die Python-Standardbibliothek. Mit einer vorhandenen Python-Version ab 3.12 kann er direkt aus dem Quellverzeichnis gestartet werden. Dieses Beispiel nutzt den Windows-Python-Launcher und Python 3.12:

```powershell
cd llm-agent-security-lab
py -3.12 -m venv .venv
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m security_lab demo --output runs/demo
```

`PYTHONPATH` gilt hier nur für das aktuelle Terminal. Verwende bei abweichender Installation den passenden Python-Interpreter. Diese Alternative installiert keine zusätzlichen Laufzeitpakete und benötigt ebenfalls kein Aktivierungsskript. Sie eignet sich für die CLI-Demo; Oberfläche und vollständige Tests benötigen zusätzliche Pakete wie im uv-Ablauf beschrieben.

## VS Code

1. Den gesamten Repository-Ordner öffnen.
2. Unter **Terminal → Aufgabe ausführen** die Aufgabe **Labor: Gesamtinstallation** starten. Sie synchronisiert die Python-Umgebung, installiert die Frontend-Pakete und baut das Frontend nacheinander.
3. Nach erfolgreichem Abschluss **Labor: Oberflaeche starten** ausführen und `http://127.0.0.1:8765` öffnen.
4. Für Python-Editorfunktionen bei Bedarf die Python-Erweiterung installieren und über **Python: Select Interpreter** `.venv\Scripts\python.exe` auswählen.

Die Aufgaben werden aus der versionierten `.vscode/tasks.json` geladen; ein Kollege muss diese Datei nicht kopieren. Git, uv und Node müssen zuvor installiert sein. [VS Code und gemeinsame Aufgaben](vscode.md) beschreibt alle Aufgaben sowie persönliche Terminal-Einstellungen; [Laboroberfläche](workbench.md) erklärt die Bedienung.

Die Windows-Aufgaben verwenden `npm.cmd`, damit PowerShell kein `npm.ps1` laden muss. Dafür sind weder eine Änderung der Ausführungsrichtlinie noch ein Administrator-Terminal erforderlich.

## Diagnose und vollständiger lokaler Check

Nach der Python-Synchronisierung hilft der ausschließlich lesende Diagnosebefehl:

```powershell
.\.venv\Scripts\python.exe -B -m security_lab.doctor
.\.venv\Scripts\python.exe -B -m security_lab.doctor --json
```

Er prüft Python 3.12 als Referenzlaufzeit, Git/uv/Node/npm, vorhandene Webpakete,
Frontend-Build und dessen Zeitstempel, Port 8765, freien Dateisystemspeicher und
Zugriffsrechte. Proxy-URLs werden auf ihre Form und konfigurierte CA-Dateien auf
Lesbarkeit geprüft. Zugangsdaten, Proxywerte und Zertifikatspfade werden nicht
ausgegeben. Fehlende Pfade werden nicht angelegt; keine Pakete installiert und
keine Dienste beendet. `-B` verhindert zusätzlich Python-Bytecode-Dateien.
Die einzige Netzwerkprobe ist eine kurze TCP-Verbindung zu `127.0.0.1` ohne
HTTP-Anfrage; es gibt keine externen Netzwerkanfragen. Ein belegter Port kann
ein korrekt laufender eigener Laborserver sein und wird deshalb als Warnung gemeldet.

Die Diagnose beweist keine Proxy-Erreichbarkeit, keine TLS-Verbindung und keine
vollständigen Windows-ACL-/Quota-Rechte. Git-/npm-Konfigurationsdateien werden
nicht ausgelesen. Hinweise zu deaktivierter TLS-Prüfung erfordern die Korrektur
der persönlichen Konfiguration; der Befehl verändert sie nicht. Speicherwarnung:
weniger als 256 MiB oder 10 Prozent frei; das Dateisystem kann größer als die
eigene Render-Disk-/Benutzerquote sein.

Installation und Test bleiben getrennt. Nach `uv sync`, `npm ci` und der
ausdrücklichen Browserinstallation im Ordner `frontend`:

```powershell
npm.cmd run browsers:install:chromium
cd ..
uv run --no-sync --locked --extra web --group dev python scripts/check_all.py
```

Der Gesamtcheck führt zuerst `uv run --locked --no-sync ruff check .` mit dem
begrenzten gemeinsamen Regelumfang aus, danach Python-Tests, React-Tests, TypeScript/Build und Chromium
nacheinander aus und stoppt bei einem Fehler. Für Firefox und WebKit zusätzlich
in `frontend` `npm.cmd run browsers:install` ausführen, danach den Gesamtcheck
mit `--all-browsers`. Die VS-Code-Aufgabe **Labor: Gesamtcheck** und JetBrains-
Terminals verwenden denselben Ablauf. Referenzlaufzeit ist Python 3.12; eine
offene Paketangabe `>=3.12` verspricht keine Abnahme jeder neueren Version.

Eine neue Windows-Installation auf Jonahs eigenem Rechner bleibt eine reale
Abnahme: frischer Clone → Synchronisierung → Diagnose → Build → Gesamtcheck →
24 Mock-Läufe → Archiv prüfen und in einen getrennten Pfad wiederherstellen.
Erst tatsächlich ausgeführte Schritte mit Betriebssystem, Commit und Ergebnis
dokumentieren. Ein Linux-Testlauf ersetzt diesen Nachweis nicht.

## IntelliJ IDEA

1. Den Repository-Ordner öffnen.
2. Das zur installierten IntelliJ-Version passende Python-Plugin aktivieren.
3. `.venv\Scripts\python.exe` als Python-SDK des Projekts auswählen.
4. Zum Einstieg dieselben Terminalbefehle wie in VS Code verwenden.

Die [JetBrains-Dokumentation](https://www.jetbrains.com/help/idea/python.html) beschreibt Plugin und Interpreter. Eine funktionierende IDE-Anbindung von Codex ist hilfreich, aber keine Voraussetzung für das Starten der Anwendung.

## Firmenlaptop und Proxy

Git, Paketdownloads und die spätere Modell-API sind getrennte Netzwerkverbindungen. Ein erfolgreicher Git-Klon beweist daher noch keinen funktionierenden Modellzugang.

- Proxywerte und gegebenenfalls erforderliche Zertifikate werden lokal nach den Vorgaben der Organisation konfiguriert.
- Unternehmensspezifische Einstellungen und Zugangsdaten gehören nicht in die gemeinsame Konfiguration.
- Persönliche Terminal-Umgebungsvariablen stehen bei direkt geöffnetem Projektordner in der ignorierten `.vscode/settings.json`. Bei einem gespeicherten Arbeitsbereich gehören sie in dessen persönliche `.code-workspace`-Datei außerhalb des Repositorys; siehe [VS-Code-Anleitung](vscode.md#persönliche-einstellungen).
- TLS-Zertifikatsprüfung bleibt aktiv. Eine fehlgeschlagene Verbindung wird behoben, indem Proxy, Zertifikate oder Freigaben korrekt eingerichtet werden.
- Die Offline-Demo funktioniert nach Bereitstellung von Code und Python ohne Modellzugang.

Bei einem Rechnerwechsel Änderungen zuerst committen und pushen, auf dem anderen Rechner holen und anschließend **Labor: Gesamtinstallation** ausführen. Für die Python-Umgebung allein genügt `uv sync --locked --extra web --group dev`. `.venv`, `node_modules` und lokale Schlüssel werden nicht zwischen Rechnern kopiert.

## Prüfung der Ausführungsumgebung

Vor echten Angriffsversuchen wird eine eigene, dokumentierte Umgebung eingerichtet. Zu prüfen sind Benutzerrechte, erreichbare Dateien, Hostfreigaben, Netzwerkziele und Ressourcenlimits. Für den Anfang bietet sich ein privater Rechner an, auf dem diese Grenzen kontrolliert eingerichtet werden können. Docker oder eine VM können dabei helfen; ihre bloße Installation bestätigt noch keine Isolation.

Die Testmodell-Demo dient zuerst der Prüfung der Anwendung. Sie ersetzt weder den späteren LLM-Pilot noch die Prüfung der Ausführungsumgebung.
