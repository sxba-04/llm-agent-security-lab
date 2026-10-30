# LLM Agent Security Lab

Praktischer Teil der Studienarbeit von Sebastian Herrmann und Jonah Häuser an der DHBW Karlsruhe, betreut von Ralf Brune. Das Labor untersucht indirekte Prompt Injection in einem Assistenten für **ausschließlich synthetische Service-Tickets**.

Der Assistent kann Tickets lesen und Notizen ergänzen. Ein externer Wissensartikel wird unverändert oder mit einer zusätzlichen Angriffsanweisung bereitgestellt. Vier Konfigurationen derselben Anwendung vergleichen Inhaltsfilterung und anwendungsseitige Autorisierung:

| Variante | Inhaltsfilter F | Autorisierung P |
|---|---|---|
| B | Aus | Aus |
| F | Ein | Aus |
| P | Aus | Ein |
| FP | Ein | Ein |

**Projektstand 0.2:** Lokale FastAPI-/React-Laboroberfläche, zwölf überarbeitete Fallpaare, kontrolliertes Testmodell, PDF-Wissensartikel, prüfbare Laufarchive und unabhängige Bewertung mit gepaarten Vergleichen. Der endgültige Testkatalog und empirische Ergebnisse mit einem echten LLM liegen noch nicht vor. Ausgaben des Testmodells sind **keine Forschungsergebnisse zur Wirksamkeit der Schutzmaßnahmen**.

## Online-Werkbank

Die [Online-Werkbank öffnen](https://sxba-04.github.io/llm-agent-security-lab/) und mit dem persönlichen Labor-Zugangscode anmelden. Dafür muss keine lokale Entwicklungsumgebung laufen. GitHub Pages liefert die Oberfläche; das geschützte [Python-Backend auf Render](https://llm-agent-security-lab-demo-api.onrender.com/healthz) führt die Anwendung aus. Die Erreichbarkeit, der Zugriffsschutz und der Free-Plan wurden am 30. Oktober 2026 erneut geprüft. Einrichtung, Prüfgrenzen und Betrieb sind unter [GitHub Pages und geschütztes Python-Backend](docs/hosting.md) dokumentiert.

**Dieser kostenlose Testbetrieb verliert hochgeladene PDFs, Versuche und Bewertungen bei Ruhezustand, Neustart oder Deployment.** Benötigte Archive vorher herunterladen; wichtige Studienbelege lokal sichern. Die Oberfläche bleibt im Mock-Betrieb. Nach einer Ruhephase kann die erste Verbindung ungefähr eine Minute dauern.

Für spätere echte Modellversuche kann das Sprachmodell beim API-Anbieter laufen. Das eigene Backend steuert die Versuche, prüft Toolvorschläge und wertet Belege aus; es benötigt dafür keine lokalen Modellgewichte oder GPU. Echte API-Aufrufe und ihre Kosten bleiben dem separat freizugebenden Pilotbetrieb vorbehalten.

## Grafische Oberfläche unter Windows

Voraussetzungen sind Git, uv und **Node.js 24 ab Version 24.15.0, kleiner als 25**. Die benötigte Python-Version kann uv bereitstellen.

In VS Code den Repository-Ordner öffnen und unter **Terminal → Aufgabe ausführen** zuerst **Labor: Gesamtinstallation**, danach **Labor: Oberflaeche starten** auswählen. Die gemeinsamen Aufgaben sind in [.vscode/tasks.json](.vscode/tasks.json) versioniert und nach dem Klonen direkt verfügbar. Sie setzen installierte Werkzeuge im `PATH` voraus. Details stehen in [VS Code und gemeinsame Aufgaben](docs/vscode.md).

Alternativ die folgenden Befehle im Repository-Verzeichnis einzeln ausführen. Bei einem Fehler zuerst dessen Ursache beheben, bevor der nächste Schritt folgt:

```powershell
uv sync --locked --extra web --group dev
cd frontend
npm.cmd ci
npm.cmd run build
cd ..
uv run --locked --extra web security-lab-web
```

Im Browser **http://127.0.0.1:8765** öffnen. Die Oberfläche startet ausschließlich kostenlose lokale Mock-Läufe. Sie zeigt Fälle, Artikel, Ticketänderungen, Laufverläufe, Vergleiche und getrennte Bewertungsformulare. Beispiel-PDFs können heruntergeladen, wieder importiert, als extrahierter Text geprüft und ausdrücklich einer Fallquelle zugeordnet werden.

[Bedienung und Einrichtung](docs/workbench.md) · [PDF-Quellen](docs/pdf-sources.md) · [Sicherung und Wiederherstellung](docs/archives.md)

Für eure gemeinsame erste Prüfung folgt der [genauen Klickanleitung mit Sollwerten](docs/manual-acceptance.md). Das [leere Prüfprotokoll](docs/manual-acceptance-record-template.md) hält eure tatsächlich beobachteten Ergebnisse und fachlichen Entscheidungen fest. [GitHub Actions](docs/github-actions.md) erklärt die automatischen Prüfungen und manuell startbaren Mock-Kampagnen.

[Zusammenarbeit und Beiträge](CONTRIBUTING.md) · [Coverage, Sonar und Sicherheitswerkzeuge](docs/quality-tooling.md)

## Schnellstart unter Windows

Voraussetzungen: Git und [uv](https://docs.astral.sh/uv/getting-started/installation/). Die Befehle werden im Terminal ausgeführt; eine virtuelle Umgebung muss nicht manuell aktiviert werden.

```powershell
git clone https://github.com/sxba-04/llm-agent-security-lab.git
cd llm-agent-security-lab
uv sync --locked --extra web --group dev
uv run --locked --extra web python -m security_lab demo --output runs/demo
uv run --locked --extra web --group dev python -m unittest discover -s tests -v
```

Die Demo verwendet das lokale, deterministische Testmodell und benötigt weder einen API-Schlüssel noch eine GPU. Sie wählt ein Fallpaar je Angriffsziel aus und erzeugt **24 technische Läufe**. Eine erfolgreiche Ausführung meldet `completed: 24/24 runs` und weist ausdrücklich auf den Mock-Betrieb hin. Verwende für einen weiteren Lauf einen neuen Ausgabeordner. Die [Windows-Anleitung](docs/setup-windows.md) erklärt VS Code, IntelliJ und eine Alternative ohne uv.

## Entwicklungsfälle ausführen

```powershell
uv run --locked --extra web python -m security_lab run --cases cases/dev --variants B F P FP --sources clean attack --repeats 1 --seed 20261022 --output runs/pilot
uv run --locked --extra web python -m security_lab summarize runs/pilot --output runs/pilot/summary.json
```

Zwölf Fälle × zwei Artikelversionen × vier Varianten × eine Wiederholung ergeben **96 technische Aufgabenläufe**. Das Testmodell folgt vorgegebenen Skripten, um erlaubte Aktionen, blockierte Aktionen, Datenoffenlegung und inhaltliche Restfälle gezielt zu prüfen. Seine Ergebnisse sagen nichts über die Angreifbarkeit eines realen Modells aus.

Für echte Modellaufrufe sind ein gesondert eingerichteter API-Zugang, geprüfte lokale Einstellungen und ein ausdrücklich gestarteter kostenpflichtiger Lauf erforderlich. Das Budget der Modell-API-Versuche beträgt höchstens **250 EUR**. Siehe [Modellzugang und Budget](docs/api.md).

## Ergebnisse lesen

Die Laufdaten unterscheiden unter anderem:

- vom Modell vorgeschlagene Tool-Aufrufe;
- Filter- und Berechtigungsentscheidungen;
- tatsächlich ausgeführte Lese- und Schreibaktionen;
- Übergabe geschützter synthetischer Daten an das Modell;
- für den Nutzer sichtbare Ausgabe und abschließenden Ticketzustand;
- technischen Laufstatus, Modellaufrufe und Aufwand.

Die Auswertung prüft Berechtigungsverletzungen unabhängig von der implementierten Policy. Inhaltliche Urteile bleiben bis zur menschlichen Bewertung offen; ein fehlendes Urteil wird nicht als erfolgloser Angriff gezählt. [Versuchsablauf und Bewertung](docs/experiment.md) beschreibt die Regeln.

Der Ablauf für menschliche Urteile ist vollständig vorbereitet: `review-export` erstellt die Unterlagen, `review-import` verbindet zwei unabhängige Bewertungen, `review-adjudicate` hält die begründete Klärung einer Abweichung fest und `summarize --reviews` berechnet daraus eine Zusammenfassung. Die Bewertungen werden anhand der Hashwerte an die ursprünglichen Läufe gebunden. `analysis/export_tables.py` exportiert daraus CSV-Tabellen. Auch bewertete Mock-Läufe bleiben technische Prüfungen.

In einem Ausgabeordner enthält `manifest.json` die Konfiguration und Reihenfolge, `records/` die vollständigen Einzelläufe, `events/` deren Ereignisse als JSONL und `summary.json` die technische Zusammenfassung. `cases.snapshot.json` bewahrt den verwendeten Fallstand. Diese Daten gemeinsam sichern, wenn ein Lauf später nachvollziehbar bleiben soll.

## Repository

| Pfad | Zweck |
|---|---|
| `src/security_lab/` | Anwendung, Tools, Filter, Modellanbindung, Auswertung und CLI |
| `cases/dev/` | Zwölf Entwicklungsfälle mit sauberem und manipuliertem Artikel |
| `cases/test/` | Platz für den später separat entwickelten Haupttestkatalog |
| `tests/` | Automatisierte technische Prüfungen ohne echte API-Aufrufe |
| `configs/` | Überprüfbare Konfigurationen und lokale API-Vorlage |
| `docs/` | Architektur, Einrichtung, Methode, Entscheidungen und Beiträge |
| `frontend/` | React-/TypeScript-Oberfläche mit Vite, Tests und Lockdatei |
| `.vscode/tasks.json` | Gemeinsame VS-Code-Aufgaben für Installation, Start und Prüfungen |
| `.github/workflows/` | Windows-/Linux-CI und manuell startbare Mock-Kampagnen |
| `scripts/ci_mock_campaign.py` | Begrenzte Mock-Kampagne mit Archivprüfung und Wiederherstellung |
| `runs/` | Lokale Laufdaten; nicht automatisch Teil der Git-Historie |

## Grenzen des Labors

Die Tools bearbeiten nur die geladenen synthetischen Daten. Sie besitzen keine Shell-, Browser-, E-Mail- oder Produktivsystem-Funktion. Bei B und F bleibt das synthetische Backend bewusst permissiv, damit ein unerlaubter Zugriff als untersuchtes Ereignis beobachtet werden kann. Syntaxprüfungen und Laufgrenzen gelten in allen Varianten.

Eine Python-Umgebung ist keine Sicherheitssandbox. Vor echten Angriffsversuchen müssen die tatsächlichen Datei-, Netzwerk- und Ressourcengrenzen der Ausführungsumgebung geprüft und dokumentiert werden. Die vorhandene Implementierung allein bescheinigt keine isolierte Umgebung.

## Zusammenarbeit

Arbeiten erfolgen in kurzen Branches mit Pull Requests und nachvollziehbarer Gegenprüfung. [Arbeitsablauf](docs/workflow.md), [Review-Einstellungen](docs/review-settings.md), [Repository-Prüfung vom 27.10.](docs/repository-audit-2026-10-27.md), [Sicherheitsgrenzen](SECURITY.md), [Entscheidungsstand](docs/decisions.md) und [Beiträge und KI-Unterstützung](docs/contributions.md) halten fest, wie technische Änderungen und wissenschaftliche Verantwortung zusammengehören.

Vor dem Zusammenführen müssen die Tests und angeforderten Reviews für den aktuellen Commit abgeschlossen und sämtliche Befunde geprüft sein; ausdrücklich genehmigte Ausnahmen werden gemäß Arbeitsablauf dokumentiert. Die vorhandenen Tests ersetzen keine abgeschlossene Gegenprüfung.

Der [Schutz von `main`](docs/branch-protection.md) verlangt Pull Requests, vier erfolgreiche CI-Jobs, einen aktuellen Basisstand und erledigte Review-Gespräche. Force-Push und Löschen sind gesperrt; es gibt keine Bypass-Liste.

Die aktuelle Implementierung wurde mit ChatGPT/Codex erstellt. Die Autoren prüfen, verstehen und überarbeiten die übernommenen Bestandteile vor der wissenschaftlichen Verwendung. Ein Commit ist kein Nachweis einer bereits erfolgten menschlichen Prüfung.
