# Modellzugang und Budget

Das Labor startet standardmäßig mit einem lokalen Testmodell. Echte Modellaufrufe sind eine gesonderte Betriebsart. Im ersten Entwicklungsstand wurden kein Modell ausgewählt, kein API-Schlüssel eingerichtet und keine kostenpflichtigen Messungen durchgeführt.

## Einmaliger A17-Pilot auf dem gehosteten Backend

GitHub Pages zeigt die Bedienoberfläche. Der vorhandene Render-Dienst führt
den gleichen sauberen A17-Lauf in Variante P aus wie die lokale CLI. Eigene
Kampagnen, Fallauswahl und PDF-Importe verwenden das Testmodell.

1. Den projektgebundenen Dienstkontoschlüssel für `gpt-6-luna` als
   `OPENAI_API_KEY` in der Umgebung des Render-Backends bereitstellen. Der
   automatisierte Build, das Frontend und die Offline-Tests benötigen ihn
   nicht. Vor jedem Deployment den Workspace extern sichern und die
   Wiederherstellung prüfen.
2. Autorenabnahme und äußere Isolation gemäß [Pilotvorprüfung](study-preflight.md)
   dokumentieren. Guthaben, aktuellen Preis, installierte Revision und den
   freigegebenen Einzelversuch prüfen. Die im Pilotcode hinterlegten
   Planraten beruhen auf der Preisprüfung vom 9. November 2026 und gelten
   jeweils pro Million Tokens (0,12 EUR Eingabe und 0,60 EUR Ausgabe).
3. Für den vereinbarten Ausführungsort den persistenten Mount, die vorhandenen
   Belege und den gemeinsamen Ledger abgleichen. Das Backend erwartet
   `LAB_STORAGE_MODE=persistent`. Erst für den überprüften Lauf
   `LAB_LUNA_PILOT_ENABLED=true` auf dem Backend aktivieren. Ein
   Konfigurationsschalter ersetzt die Prüfung der äußeren Isolation nicht.
4. Ein angemeldeter Labor-Operator startet den festgelegten Pilot über die
   Weboberfläche einmal. Vier Modellanfragen, drei Werkzeugaufrufe und
   0,50 EUR bilden die Obergrenze. Für die fachliche Bewertung prüfen die
   Autoren die Antwort auf die drei verlangten Fakten.

Das geschützte `GET /api/pilot/luna` zeigt den Zustand und nach Abschluss die
Antwort, beobachtete Modellkennung, Anzahlen der Modell- und Werkzeugaufrufe,
Eingabe- und Ausgabetokens sowie die aus den Planraten ermittelten Kosten.
Fehlt ein Verbrauchsbeleg, bleiben Tokensummen und Kosten offen. Bestätigte
Tokenzahlen bleiben auch bei abweichendem Modell, Tarif oder gescheiterter
Budgetbuchung sichtbar. In diesen Fällen entfällt die Kostenschätzung. Die
Abrechnung des Anbieters ist für die endgültige Kostenprüfung maßgebend.

`POST /api/pilot/luna` ist der explizite einmalige Start. Die Anfrage hat
keinen Body und keine Query-Parameter und benötigt die zugelassene Origin,
Operator-Anmeldung und das Sitzungstoken. Bei belegtem Versuch oder laufender
Sicherung liefert sie HTTP 409, bei deaktiviertem Pilot HTTP 503. Nach einem
Verbindungsabbruch den Status mit GET abfragen. Ein zweiter Start, auch nach
einem Dienstneustart, bleibt gesperrt, sobald ein Versuchsordner existiert.
Bei fehlenden oder beschädigten Belegen bleibt der Status offen bzw.
fehlgeschlagen. Nach dem Deaktivieren bleiben vorhandene Ergebnisse lesbar.

Auf dem konfigurierten Mount liegen `studies/budget.json` und
`studies/luna-clean-first/` unter `LAB_WORKSPACE`. Für einen Abgleich mit der
CLI ist exakt dieser `studies`-Ordner deren Budget-Workspace. Eine
Workspace-Sicherung wartet keine Modellantwort ab und weist sich überschneidende
Pilotstarts oder Sicherungen zurück. Sie enthält die Pilotbelege getrennt von
den wissenschaftlichen Kampagnen. Ein nach einem Abbruch völlig leerer
Versuchsordner verhindert eine Sicherung, weil ein reines Dateiarchiv seine
Startsperre nicht wiederherstellen könnte. Die gehostete Anbindung und die
netzwerkfreien Regressionstests wurden mit Codex entwickelt.

## Lokale technische Abnahme mit GPT-6 Luna

Der erste Lauf beantwortet genau eine saubere Aufgabe aus dem festgelegten
Entwicklungsfall `DEV-G1-01`. Die CLI prüft die Originaldatei anhand ihres
SHA-256, übernimmt nur den sauberen Artikel und verwendet den gemeinsamen
Ticket-Gateway in Variante P. Dieser Fall erlaubt das Lesen von A17 und keine
Änderungen. Der Modellzugang ist auf diesen lokalen Ablauf beschränkt. Ein
erfolgreicher Transport und eine autorisierte Ticketabfrage belegen die technische
Anbindung. Für das Kriterium von zehn korrekten Aufgaben in B sind die gesonderte
Serie und die Bewertung durch die Autoren erforderlich.

Der Anbieter nennt für das Standardmodell am 9. November 2026 je Million Tokens
0,10 USD für Eingaben und 0,50 USD für Ausgaben. Quelle und Modellkennung sind
auf der [Modellseite](https://developers.openai.com/api/docs/models/gpt-6-luna)
dokumentiert. Für das folgende Planbeispiel ergeben sich bei einem angenommenen
Verhältnis von 1 USD zu 1 EUR plus 20 Prozent Reserve 0,12 und 0,60 EUR.
Vor der Ausführung Preise, Wechselkurs und Steuerreserve prüfen und die
tatsächlich angesetzten Werte samt Prüftag einsetzen. Die lokale Reservierung
bewertet auch gecachte Eingaben zum vollen Eingabepreis.

Die Vorschau ist offline und benötigt keinen Schlüssel. Die folgenden Befehle
sind für PowerShell im Checkout geschrieben.

```powershell
$rates = @("--input-eur-per-million", "0.12", "--output-eur-per-million", "0.60", "--price-checked-on", "2026-11-09")
uv run --no-env-file --locked --extra web python -m security_lab.luna_pilot plan @rates
```

Die [Pilotvorprüfung](study-preflight.md#kosten-und-offene-freigaben-sichtbar-machen)
verlangt Autorenabnahme, Nachweis der äußeren Isolation, geprüfte externe
Wiederherstellung und Freigabe des konkreten Laufs. Nach Abgleich des
Projekt-Ledgers und des Anbieterzugangs den projektspezifischen Schlüssel als
`OPENAI_API_KEY` in der lokalen, von Git ignorierten Datei `.env.local`
bereitstellen. Der Startbefehl lädt diese Datei mit `--env-file`. Eine bereits
in der Shell gesetzte Variable hat Vorrang. Für den Dateizugang daher eine
Shell ohne anderweitig gesetzten `OPENAI_API_KEY` verwenden. Liegt die Datei
in einem anderen Checkout, ihren absoluten Pfad an `--env-file` übergeben
und mit `--workspace` dasselbe dauerhafte
`runs`-Verzeichnis wie für die bestehenden bezahlten Läufe wählen.
Das Workspace-Verzeichnis bestimmt gleichzeitig Ledger und Evidenzablage.

```powershell
uv run --env-file .env.local --locked --extra web python -m security_lab.luna_pilot run-first @rates --allow-paid-api --isolation-acknowledged
```

Die festen technischen Grenzen sind vier Modellanfragen mit jeweils höchstens
32.768 konservativ geschätzten Eingabe- und 1.024 Ausgabetokens, drei
Werkzeugaufrufe und insgesamt 0,50 EUR. Mit den Beispielraten und voll
ausgeschöpften Tokengrenzen ergibt sich ein Planwert von 0,00454656 EUR
pro Anfrage und 0,01818624 EUR für vier Anfragen. Den tatsächlichen Verbrauch
liefern erst die Antworten des Anbieters. Der Aufruf verwendet Chat Completions
mit `reasoning_effort=none`, `service_tier=default`, `parallel_tool_calls=false`
und `store=false`.
Modellantworten können mehrere Anfragen für dieselbe Ticketaufgabe erfordern.
Jede Anfrage reserviert vor dem Versand einen Betrag im gemeinsamen
`budget.json`. Bei unklarem Transportausgang bleibt die Reservierung bestehen.

Unter `luna-clean-first/` enthält `attempt.json` vor der ersten Anfrage den
Fallhash, die Parameter und die Codeprovenienz. Das exklusiv angelegte
Versuchsverzeichnis sperrt auch nach Abbruch jeden erneuten Start im selben Workspace. `result.json` enthält
Ereignisse, zurückgemeldetes Modell, Tokenverbrauch und Laufstatus.
Die technische Abnahme erfordert eine abgeschlossene Antwort mit Text und den
belegten Rückweg der A17-Daten in den Modellkontext. Eine unvollständige
Verbrauchsmeldung, Budgetüberschreitung oder unerwartete Modellkennung stoppt
den Lauf vor weiteren Werkzeugen und Modellanfragen. Der Pilot fordert stets
den Alias `gpt-6-luna` an. Die erste Antwort darf diesen Alias oder einen
Snapshot derselben Familie im Format `gpt-6-luna-YYYY-MM-DD` mit gültigem
Kalenderdatum melden. Ihre genaue Kennung wird für alle weiteren Antworten
dieses Ticketlaufs festgehalten. Ein späterer Wechsel beendet den Lauf vor der
Ausführung weiterer Werkzeuge. Die jeweilige Originalkennung steht im
Ereignisprotokoll.
`receipt.json` bindet die gespeicherten Dateien über Hashwerte zusammen.
Bei fehlendem Ergebnis oder offener Reservierung die Originalbelege erhalten
und die Nutzung beim Anbieter abgleichen. Die Autoren bewerten die inhaltliche
Richtigkeit anhand der drei geforderten Fakten. Die Implementierung und ihre
netzwerkfreien Tests entstanden mit Codex.

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
