# GitHub Actions: automatische Prüfung und manuelle Mock-Läufe

GitHub Actions führt die in `.github/workflows/` beschriebenen Aufgaben auf vorübergehenden GitHub-Rechnern aus. Jeder Job erhält eine frische Umgebung, lädt den gewählten Repository-Stand und installiert die festgelegten Abhängigkeiten. Nach dem Job wird der Rechner entfernt. Das Team muss dafür keinen eigenen Server betreiben.

Die Anwendung läuft dort bereits für Tests: Ein Python-Prozess startet FastAPI, Chromium bedient die React-Oberfläche, und die Ergebnisse werden überprüft. Ein weiterer Ablauf führt synthetische Kampagnen aus. Diese Prozesse liefern **keinen dauerhaften, öffentlich erreichbaren Laborserver**. GitHub Pages kann statische Dateien ausliefern, aber das benötigte Python-/FastAPI-Backend nicht ausführen. Für eure interaktive Arbeit bleibt der lokale Start über die [VS-Code-Aufgaben](vscode.md) vorgesehen.

## 1. Automatische Prüfungen ansehen

1. Das Repository in GitHub öffnen und oben **Actions** wählen.
2. Links **Offline tests** auswählen.
3. Den Durchlauf des gewünschten Pull Requests beziehungsweise Commits öffnen. Commit und Branch kontrollieren, damit ein älterer grüner Durchlauf nicht mit einer neuen Änderung verwechselt wird.
4. In der Zusammenfassung die vier Jobs öffnen:

| Check | Tatsächlicher Umfang |
|---|---|
| `test (ubuntu-latest)` | Python-Tests, 96 Mock-Läufe, Neuberechnung, Bewertungsmaterial, Archivprüfung, Wiederherstellung und erneute Auswertung unter Linux. |
| `test (windows-latest)` | Derselbe Ablauf unter Windows, einschließlich der dort ausführbaren Dateisperrenprüfung. |
| `frontend (ubuntu-latest)` | Saubere npm-Installation, React-Tests, TypeScript/Build, echter Chromium-Browser mit FastAPI unter Linux. |
| `frontend (windows-latest)` | Derselbe Frontend-/Browserablauf unter Windows. |

Erwartung: Alle vier Jobs enden erfolgreich. Die Jobzusammenfassungen nennen die tatsächlich gemeldeten Teilergebnisse (`success`, `failure` oder `skipped`). Übersprungene oder fehlgeschlagene Schritte sind keine bestandenen Prüfungen. Die Mock-Zusammenfassung nennt die geplanten und abgeschlossenen Läufe und weist ausdrücklich auf rein technische Ergebnisse hin.

Der Workflow startet bei Pull Requests, bei Änderungen auf `main` und auf ausdrücklichen manuellen Start. Ein neuer Stand desselben PRs beendet einen noch laufenden älteren CI-Durchlauf. Es werden keine identischen zusätzlichen Feature-Branch-Push-Prüfungen gestartet. Codex- und Copilot-Reviews bleiben eigenständige Prüfungen; eine grüne CI ersetzt sie nicht.

Den kompletten Prüfstand manuell starten: **Actions → Offline tests → Run workflow → Branch auswählen → Run workflow**. Für den gemeinsamen freigegebenen Stand `main` auswählen. Der Button ist verfügbar, wenn der Workflow auf dem Standardbranch liegt und der angemeldete Account Schreibrechte besitzt.

## 2. Eine Mock-Kampagne bei GitHub ausführen

1. **Actions → Mock campaign** öffnen.
2. **Run workflow** wählen.
3. Als Branch **main** wählen.
4. Unter **Synthetic cases per repetition** eines der beiden festen Programme auswählen.
5. Unter **Repetitions** `1`, `2` oder `3` auswählen.
6. Mit **Run workflow** starten, den neuen Durchlauf öffnen und dessen Ende abwarten.

| Auswahl | Fälle und Bedingungen | Läufe bei 1 / 2 / 3 Wiederholungen |
|---|---|---|
| `demo24` | Ein repräsentativer Entwicklungsfall je Angriffsziel, beide Quellen, B/F/P/FP. | 24 / 48 / 72 |
| `catalog96` | Alle zwölf Entwicklungsfälle, beide Quellen, B/F/P/FP. | 96 / 192 / 288 |

Für den ersten Versuch `demo24` und `1` verwenden. Erwartet werden **24/24 abgeschlossene Läufe**, ausschließlich Mock-Betrieb sowie erfolgreiche Archiv- und Wiederherstellungsprüfung. Die Wiederholungen erzeugen keine neuen unabhängigen Basisfälle und keine empirischen Aussagen zur Angreifbarkeit eines LLM.

Die Eingaben werden zusätzlich im Python-Helfer gegen die festen Auswahlmengen geprüft. Sie werden als Daten übernommen und nicht in Shellbefehle eingesetzt. Es gibt keine Eingabe für API-Schlüssel, Modellanbieter, freie Befehle oder beliebige Falldateipfade. Der Job verwendet Standard-Ubuntu, ein Zeitlimit von 15 Minuten und ein Repository-Token mit Leserechten. Die festgelegten Action-Versionen und Lockdateien entsprechen der normalen CI.

## 3. Ergebnisse herunterladen und lesen

Im abgeschlossenen Durchlauf unter **Artifacts** das gewünschte Paket herunterladen und das äußere ZIP entpacken. Für Downloads ist eine GitHub-Anmeldung mit Lesezugriff erforderlich.

| Artefakt | Inhalt und Verwendung |
|---|---|
| `mock-evidence-Linux` / `mock-evidence-Windows` | Synthetische Belege der automatischen 96-Lauf-Prüfung. |
| `manual-mock-evidence` | Belege des ausdrücklich gestarteten Mock-Programms. |
| `browser-evidence-Linux` / `browser-evidence-Windows` | Playwright-Berichte, gespeicherte Ansichten und gegebenenfalls Fehlerbelege. |
| `unverified-mock-diagnostics-Linux` / `unverified-mock-diagnostics-Windows` / `unverified-mock-diagnostics-manual` | Nur bei fehlgeschlagenem oder abgebrochenem Kampagnenschritt: vorhandenes Manifest, Fallsnapshot, Laufdatensätze, Ereignisse und Review-Teilstände zur Fehleranalyse. Kein erfolgreich verifiziertes Archiv. |
| `frontend-build` | Einmalig unter Linux gebauter Inhalt von `frontend/dist`; benötigt den passenden Python-Backendstand. Kein eigenständig funktionierender Laborserver. |

Ein erfolgreiches Mock-Belegpaket enthält:

- **`campaign.zip`**: vollständige synthetische Kampagne mit Manifest, Fallsnapshot, Laufdatensätzen, Ereignissen und unbewerteten Review-Paketen/CSV-Vorlagen. Die Review-Dateien liegen innerhalb der Kampagne und werden mitgesichert.
- **`summary.json`** und **`restored-summary.json`**: getrennt berechnete Auswertungen aus Original und Wiederherstellung; der Helfer verlangt übereinstimmende Ergebnisse.
- **`metrics.csv`**: Zähler, Nenner und offene Urteile für die Tabellenansicht. Fehlende menschliche Urteile bleiben offen.
- **`verification.json`**: Ergebnis der Archivprüfung einschließlich Vollständigkeit und Integrität; keine digitale Signatur oder bestätigte Urheberschaft.
- **`result.json`**: Preset, Wiederholungen, Abschlussstatus und beim Erfolg Codecommit sowie Archivhash.

Bei einem Fehler können nur Teilbelege vorliegen. Falls der Kampagnenschritt vor dem fertigen `campaign.zip` scheitert, werden die vorhandenen Rohbelege zusätzlich als ausdrücklich **unverified** benanntes Diagnoseartefakt hochgeladen. Das gilt auch für einen abgebrochenen Schritt, soweit der Runner den Upload noch ausführen kann. Diese Daten können unvollständig oder beschädigt sein; sie werden nicht als erfolgreich verifiziertes Kampagnenarchiv oder gültiges Messergebnis ausgegeben. Es werden ausschließlich die aufgeführten Kampagnenpfade erfasst, niemals das gesamte Arbeitsverzeichnis. Ein fehlgeschlagener Job bleibt fehlgeschlagen; `completed: false` kennzeichnet einen nicht vollständig geprüften Kampagnenlauf. Die bloße Existenz eines Artefakts bedeutet keinen Erfolg. Originaldaten werden bei Wiederholung nicht weiterverwendet: Jeder Actions-Job startet mit einem frischen Arbeitsverzeichnis.

**Aufbewahrung: 14 Tage.** Wichtige Belege vorher herunterladen und separat sichern. GitHub-Artefakte sind kein dauerhaftes Forschungsarchiv. Das Kampagnenarchiv enthält keinen vollständigen Quellcode; den zugehörigen Commit einschließlich Lockdateien zusätzlich sichern. Bei PR-Prüfungen kann der aufgezeichnete Checkout-Commit ein von GitHub erzeugter Test-Merge-Commit sein; deshalb auch PR-Head, Durchlauflink und spätere Merge-ID festhalten.

Das innere `campaign.zip` kann mit der bestehenden CLI überprüft und in einen **neuen** lokalen Ordner wiederhergestellt werden. Beispiel im Repository-Verzeichnis, nachdem das heruntergeladene ZIP außerhalb von `runs/` entpackt wurde:

```powershell
uv run --locked --extra web python -m security_lab verify-archive "C:\Pfad\zum\entpackten\campaign.zip"
uv run --locked --extra web python -m security_lab restore-archive "C:\Pfad\zum\entpackten\campaign.zip" --output runs/actions-demo-restored
```

`C:\Pfad\zum\entpackten\campaign.zip` durch den tatsächlichen lokalen Pfad ersetzen. Für einen weiteren Restore einen neuen Zielordner wählen. Die vorhandenen Review-CSV-Vorlagen gehören zum CLI-Bewertungsablauf; für die Bewertung in der Oberfläche bei der wiederhergestellten Kampagne einen neuen Bewertungssatz exportieren. Details zum Belegumfang stehen in [Archive](archives.md).

## 4. Sichtbarkeit und Kosten

Das Repository ist zum Stand 29. Oktober 2026 öffentlich. Workflow-Protokolle und die bereitgestellten synthetischen Artefakte sind entsprechend zugänglich; keine privaten Tickets, Firmenunterlagen, Schlüssel oder persönlichen Konfigurationen in diese Abläufe aufnehmen. Die Workflows laden ausschließlich ausdrücklich benannte Ausgabedateien hoch, nicht das gesamte Arbeitsverzeichnis.

Standard-GitHub-Runner für öffentliche Repositories werden nach der aktuellen GitHub-Dokumentation kostenlos bereitgestellt. Artefakt- und Cachespeicher haben eigene Grenzen; die kurze Aufbewahrung begrenzt den Speicherverbrauch. Es werden keine kostenpflichtigen größeren Runner oder echte Modell-API-Aufrufe eingerichtet. Das Modellversuchsbudget der Studienarbeit bleibt davon getrennt. Konto- und Abrechnungseinstellungen wurden durch diese Workflows nicht geändert.

## Offizielle Referenzen

Geprüft am 29. Oktober 2026:

- [GitHub-hosted Runner: Bereitstellung und Ende eines Jobs](https://docs.github.com/en/actions/how-tos/manage-runners/github-hosted-runners/use-github-hosted-runners)
- [Workflows manuell starten](https://docs.github.com/actions/managing-workflow-runs/manually-running-a-workflow)
- [Artefakte sichern und Aufbewahrung konfigurieren](https://docs.github.com/en/actions/tutorials/store-and-share-data)
- [Workflow-Artefakte herunterladen](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts)
- [Actions-Abrechnung](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [GitHub Pages unterstützt keine serverseitige Python-Anwendung](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site)
- [Unvertrauenswürdige Werte und Script-Injection](https://docs.github.com/en/actions/concepts/security/script-injections)
