# Einrichtung unter Windows

Die Anwendung wird auf jedem Rechner aus demselben Git-Repository gestartet. Jeder Rechner besitzt eine eigene Projektumgebung und lokale Zugangsdaten. Ein gemeinsamer Server oder eine GPU ist für die technischen Tests und den API-Betrieb nicht erforderlich.

## Einrichtung mit uv

Installiere Git und uv über einen auf dem jeweiligen Rechner erlaubten Weg. Die [uv-Dokumentation](https://docs.astral.sh/uv/getting-started/installation/) beschreibt die verfügbaren Installationswege. Auf einem verwalteten Firmenrechner gelten dessen Installations- und Netzwerkvorgaben.

```powershell
git clone https://github.com/sxba-04/llm-agent-security-lab.git
cd llm-agent-security-lab
uv sync --locked
uv run python -m security_lab --help
uv run python -m security_lab demo --output runs/demo
uv run python -m unittest discover -s tests -v
```

`uv sync --locked` verwendet die versionierten Abhängigkeiten. Änderungen an der Lockdatei gehören in einen überprüften Commit. Wenn die benötigte Python-Version fehlt, kann uv einen Download benötigen; auch dieser muss durch die lokale Netzwerkkonfiguration zugelassen sein.

Weder `Activate.ps1` noch das Abschalten von PowerShell-Schutzfunktionen sind für diesen Ablauf erforderlich.

## Alternative mit vorhandenem Python

Der Anwendungskern verwendet die Python-Standardbibliothek. Mit einer vorhandenen Python-Version ab 3.12 kann er direkt aus dem Quellverzeichnis gestartet werden. Dieses Beispiel nutzt den Windows-Python-Launcher und Python 3.12:

```powershell
cd llm-agent-security-lab
py -3.12 -m venv .venv
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m security_lab demo --output runs/demo
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`PYTHONPATH` gilt hier nur für das aktuelle Terminal. Verwende bei abweichender Installation den passenden Python-Interpreter. Diese Alternative installiert keine zusätzlichen Laufzeitpakete und benötigt ebenfalls kein Aktivierungsskript.

## VS Code

Die optionale FastAPI-/React-Oberfläche benötigt zusätzlich Node.js 24. Installation, Build und Start stehen in [Laboroberfläche](workbench.md). Die bestehenden CLI-Befehle bleiben nutzbar; für den vollständigen Testumfang mit PDF- und HTTP-Prüfungen `uv sync --locked --extra web --group dev` ausführen.

1. Den gesamten Repository-Ordner öffnen.
2. Die Python-Erweiterung installieren, falls sie fehlt.
3. Über **Python: Select Interpreter** den Interpreter `.venv\Scripts\python.exe` auswählen.
4. Befehle aus dem Schnellstart im integrierten Terminal ausführen.

Gemeinsame Startbefehle stehen in der README. Persönliche IDE-Einstellungen und maschinenabhängige Pfade werden nicht als Projektvorgaben eingecheckt.

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
- TLS-Zertifikatsprüfung bleibt aktiv. Eine fehlgeschlagene Verbindung wird behoben, indem Proxy, Zertifikate oder Freigaben korrekt eingerichtet werden.
- Die Offline-Demo funktioniert nach Bereitstellung von Code und Python ohne Modellzugang.

Bei einem Rechnerwechsel Änderungen zuerst committen und pushen, auf dem anderen Rechner holen und anschließend `uv sync --locked` ausführen. `.venv` und lokale Schlüssel werden nicht zwischen Rechnern kopiert.

## Prüfung der Ausführungsumgebung

Vor echten Angriffsversuchen wird eine eigene, dokumentierte Umgebung eingerichtet. Zu prüfen sind Benutzerrechte, erreichbare Dateien, Hostfreigaben, Netzwerkziele und Ressourcenlimits. Für den Anfang bietet sich ein privater Rechner an, auf dem diese Grenzen kontrolliert eingerichtet werden können. Docker oder eine VM können dabei helfen; ihre bloße Installation bestätigt noch keine Isolation.

Die Testmodell-Demo dient zuerst der Prüfung der Anwendung. Sie ersetzt weder den späteren LLM-Pilot noch die Prüfung der Ausführungsumgebung.
