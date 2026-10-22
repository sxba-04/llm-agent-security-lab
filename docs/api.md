# Modellzugang und Budget

Das Labor startet standardmäßig mit einem lokalen Testmodell. Echte Modellaufrufe sind eine gesonderte Betriebsart. Im ersten Entwicklungsstand wurden kein Modell ausgewählt, kein API-Schlüssel eingerichtet und keine kostenpflichtigen Messungen durchgeführt.

## Zugang vorbereiten

1. Einen für das Projekt nutzbaren API-Zugang einrichten.
2. Ein Modell mit passender Tool-Unterstützung und nachvollziehbarer Modellkennung auswählen.
3. `configs/api.example.json` nach `configs/api.local.json` kopieren und die lokalen Werte nach Prüfung eintragen.
4. Den API-Schlüssel als lokale Umgebungsvariable `OPENAI_API_KEY` bereitstellen.
5. Die Ausführungsumgebung prüfen und erst danach einen kleinen echten Entwicklungsversuch starten.

Die Beispielkonfiguration ist absichtlich nicht sofort für bezahlte Aufrufe verwendbar. Modell und Preise müssen ausdrücklich gesetzt werden. `.env.example` beschreibt den erwarteten Variablennamen; eine `.env`-Datei wird nicht automatisch geladen. Schlüssel nicht in Befehlsdateien, Git, Screenshots oder Laufprotokollen speichern.

| Konfigurationsfeld | Bedeutung |
|---|---|
| `enabled` | Erst nach vollständiger Einrichtung auf `true` setzen |
| `model` | Exakte Modellkennung des vorgesehenen Piloten |
| `expected_returned_model` | Optional: erwartete vom Anbieter zurückgemeldete Modellkennung für den Vergleich mehrerer Messserien |
| `input_eur_per_million`, `output_eur_per_million` | Geprüfte Preise einschließlich geplanter Umrechnungs- und Kostenreserve |
| `price_reference`, `price_checked_on` | Herkunft und Datum der Preisprüfung |
| `run_budget_eur` | Kostenobergrenze für den gesamten CLI-Aufruf, nicht je Ticketaufgabe |
| `max_requests` | Maximale Modellanfragen für den gesamten CLI-Aufruf |
| `max_completion_tokens` | Maximale Ausgabetokens je Modellanfrage |
| `max_input_tokens` | Obergrenze für die konservative Eingabeschätzung des Adapters |
| `timeout_seconds` | Zeitlimit einer einzelnen HTTP-Anfrage |

Die Vorlage begrenzt den ersten Aufruf auf 0,50 EUR und zwölf Modellanfragen. Ein voller Katalog kann diese Grenze deshalb vorzeitig erreichen. Eine Erhöhung erfolgt erst nach geprüftem Verbrauch und einer nachvollziehbaren Budgetplanung. Modellabhängige Samplingparameter werden nur gesetzt, wenn das gewählte Modell sie unterstützt.

Die Anwendung protokolliert zusätzlich die vom Anbieter tatsächlich zurückgemeldete Modellkennung. Innerhalb einer Messserie muss diese Kennung gleich bleiben. Mit `expected_returned_model` kann dieselbe Erwartung auch über mehrere Serien festgelegt werden. Bei einer Abweichung werden die Antwortdaten als Beleg gespeichert und die Serie angehalten. Das erkennt Änderungen der zurückgemeldeten Kennung; unangekündigte Änderungen hinter einer unveränderten Kennung kann diese Prüfung nicht ausschließen.

Die API-Anbindung verwendet den festen OpenAI-Endpunkt für Chat Completions und eigene Funktionen für die beiden Ticket-Tools. Der Modellvorschlag wird weiterhin von der Anwendung geprüft. Anbieterseitige Tools für Browser, Shell oder Dateien werden nicht freigeschaltet.

## Kosten planen

Das vereinbarte Gesamtbudget beträgt höchstens **250 EUR** einschließlich Entwicklung, Pilot und Hauptmessung. Zunächst wird eine kleine Teilgrenze für den echten Pilot verwendet. Aus den tatsächlich erfassten Modellanfragen und Tokenwerten wird der restliche Aufwand hochgerechnet.

Aktuelle Eingabe- und Ausgabepreise werden für die gewählte Modellkennung geprüft und als EUR-Werte mit dokumentierter Umrechnung und Reserve eingetragen. Die Beispielkonfiguration erfindet keine Preise. Mögliche Steuern, Wechselkursschwankungen und weitere Kosten werden bei der Reserve berücksichtigt.

Das lokale Budgetprotokoll reserviert vor einer Anfrage einen konservativ berechneten Betrag. Unklare Fehler können eine kostenpflichtige Anfrage nicht sicher ausschließen; dafür bleibt die Reservierung bestehen. Reservierungen sind eine technische Schutzmaßnahme, keine Garantie über die tatsächliche Anbieterrechnung. Die Abrechnung und verbleibenden Mittel werden zusätzlich im Anbieterkonto kontrolliert.

Ein lokales Budgetprotokoll ist nur auf dem Rechner wirksam, auf dem es liegt. Für bezahlte Messungen wird deshalb zunächst **ein festgelegter Ausführungsrechner mit einem gemeinsamen fortlaufenden Budgetprotokoll** verwendet. Separate lokale Protokolle auf mehreren Rechnern teilen keine globale Obergrenze. Vor einem Rechnerwechsel müssen bisherige Ausgaben und reservierte Beträge nachvollziehbar übernommen werden.

## Echte Läufe ausdrücklich starten

Der CLI-Aufruf für echte Läufe erfordert die Auswahl `--provider openai`, eine gültige lokale API-Konfiguration sowie die Schalter `--allow-paid-api` und `--isolation-acknowledged`. Diese Schalter dokumentieren einen bewussten Start. Sie richten selbst keine Sandbox ein und bestätigen keine technisch nachgewiesene Isolation.

Die genaue verfügbare Syntax zeigt:

```powershell
uv run python -m security_lab run --help
```

Beim ersten Pilot wird ein einzelner Entwicklungsfall mit geringer Wiederholungszahl verwendet. Bezahlte Anfragen werden im Entwicklungsstand nicht automatisch wiederholt. Automatische Tests und CI verwenden ausschließlich Testmodelle beziehungsweise simulierte API-Antworten.

## Quellen für die technische Anbindung

- [OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI Chat Completions API](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
- [OpenAI API-Preise](https://developers.openai.com/api/docs/pricing)

Modellzugang und Preise werden vor dem echten Pilot erneut anhand des verwendeten Kontos und der aktuellen Anbieterangaben geprüft.
