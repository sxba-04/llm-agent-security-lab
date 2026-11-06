# Ressourcenprobe und Entscheidung zur Speicherung

Die Werkbank bleibt vorerst bei ihren kanonischen JSON-/JSONL-Belegen. Ein
SQLite-Index wird erst umgesetzt, wenn gemessene Listen-/Suchzeiten auf dem
tatsächlich verwendeten Dienst einen Nutzen belegen. Ein Index müsste aus
den Originalbelegen einschließlich versionierter Namen/Tags wiederaufbaubar sein.

## Reproduzierbarer lokaler Prüfstand

Nach der getrennten Installation der Web-/Testpakete aus dem Repository-Stamm:

```powershell
uv run --no-sync --locked --extra web --group dev python scripts/performance_probe.py
```

Optional kann `--output PFAD.json` einen **neuen** Bericht in ein vorhandenes
Verzeichnis schreiben. Bestehende Dateien werden nicht überschrieben. Der
Prüfstand akzeptiert keinen Workspace-/Service-Parameter: Er erzeugt einen
temporären Workspace, führt ausschließlich synthetische Mock-Läufe aus und
entfernt diesen Workspace anschließend. Keine Live-Daten, Provideraufrufe,
kostenpflichtigen Dienste oder geänderten Host-Ressourcenlimits.

Die Standardprobe erzeugt einen validen Acht-Läufe-Mock als Ausgangsbestand und
vervielfältigt seine Dateien auf 1, 10 und 30 Kampagnen. Das sind bewusst
identische Speicherlast-Fixtures, keine unabhängigen Messungen von Modellverhalten.
Für jede Größe werden die echte FastAPI-Listenroute einmal mit leerem
Anwendungscache und fünfmal mit gefülltem Cache aufgerufen. Betriebssystemcaches
werden nicht geleert. Hinzu kommen ein 40-seitiges synthetisches Text-PDF, ein
180.000-Zeichen-Artikel mit vollständigen Laufbelegen und ein überlappender
Kampagnenstart. Für Letzteren hält ein Event den ersten Mock-Schritt an; die
echte HTTP-Route muss den zweiten Start mit 409 ablehnen.

Grenzen der CLI: höchstens 100 Kampagnen, zehn warme Stichproben, 50 PDF-Seiten
und 200.000 Artikelzeichen. Das ist kein allgemeiner Lastgenerator.
`--campaigns 1 25 100 --samples 5` erweitert gezielt die Listenprobe.

## Ausgeführte lokale Messung

Am 6. November 2026, 09:30 Uhr MEZ, auf Linux x86-64 mit Python 3.12.14
ausgeführt. Der [Rohbericht](performance/2026-11-06-local.json) enthält Parameter,
Quellhashes, Harness-Hash und den zu diesem Zeitpunkt **uncommitteten** Arbeitsstand
auf Basis von `079babd70eb38152c188fc71a355b8a19420c937`. Die Werte belegen diesen
Prüfstand und sind kein Benchmark des finalen Releases.

| Kampagnen mit je 8 Läufen | Leerer Anwendungscache | Warmer Median, 5 Abrufe | Maximalwert warmer Abrufe |
|---|---:|---:|---:|
| 1 | 17,126 ms | 3,282 ms | 3,769 ms |
| 10 | 131,937 ms | 13,029 ms | 15,217 ms |
| 30 | 457,728 ms | 40,940 ms | 50,952 ms |

| Zusätzliche Probe | Beobachtung |
|---|---|
| PDF-Import | 40 Seiten, 97.517 Bytes, 70.109 Textzeichen, 215,803 ms; Text nicht als Studienquelle bestätigt |
| Lange Belege | 180.000 Artikelzeichen; Records-Antwort 1.089.922 Bytes, 53,262 ms |
| Zweiter paralleler Start | HTTP 409 nach 5,098 ms |
| Temporärer Bestand | 586 Dateien, 11.155.775 Bytes |
| Gesamter Prüfstand | 1,490 s Laufzeit |
| Peak-RSS des Python-Hauptprozesses | 56,598 MiB |

Die Requests laufen über ASGI/TestClient im Prozess; TCP, TLS, Browserrendering
und die Render-Infrastruktur sind nicht enthalten. `getrusage` misst einen
Höchstwert über die Prozesslebenszeit. Der getrennte Höchstwert beendeter
Kindprozesse umfasst unter anderem PDF-Extraktion und Git-Aufrufe; beide Werte
dürfen nicht als gleichzeitig belegter Gesamtspeicher addiert werden. Unter
Windows wird dieser Wert ausdrücklich als nicht verfügbar ausgegeben.

Die Messung erzwingt **kein 512-MiB-Limit**. Sie weist weder eine produktive
512-MiB-Abnahme noch Windows-Kompatibilität dieser Ausführungsumgebung nach.
Einzelne synthetische Proben ersetzen keine Produktionsmessung. Die lokal
beobachteten warmen Listenzeiten begründen derzeit keinen Datenbankwechsel;
der deutlich teurere erste Abruf ist bei wachsendem echten Bestand weiter zu
beobachten.

## Beobachtete Render-Basislast

Für den bestehenden Dienst `srv-dbhmac67bikc73f0cvug` wurden am 6. November 2026
über die Render-Metrikschnittstelle (`get_metrics`) im Fenster **08:29–09:29 Uhr
MEZ** (07:29–08:29 UTC) 13 Stichproben im Fünfminutenabstand abgerufen:

| Metrik | Beobachteter Bereich |
|---|---:|
| CPU-Nutzung | 0,00162–0,00176 CPU-Kerne |
| Arbeitsspeicher | 72.822.780–73.846.780 Bytes |
| Gemeldetes Speicherlimit | 536.870.900 Bytes |
| Instanzen | 1 |
| HTTP-Latenz | Keine Messwerte zurückgegeben |

Das Fenster betrifft Leerlauf beziehungsweise leichte Bedien-/Anmeldeaktivität,
keine kontrollierte synthetische Produktionslast. Es belegt weder PDF-Spitzenlast
noch verfügbare Kapazität für größere Kampagnen. Für Latenzen wird aus der leeren
Metrik keine erfolgreiche Prüfung abgeleitet. Die Zahlen sind getrennt vom
lokalen ASGI-Prüfstand zu interpretieren.

## Nächste Betriebsbeobachtung

Auf dem vorhandenen Render-Dienst CPU, RAM, Antwortzeiten und freien Speicher
während eines begrenzten Mock-/PDF-Ablaufs beobachten; vorhandene Belege zuerst
extern sichern. Datum, Deploy-Commit, tatsächliche Ressourcenbegrenzung und
Messmethode gemeinsam dokumentieren. Kein Upgrade aufgrund dieses lokalen
Berichts. Bei wiederholt langsamen Listen zuerst Dateizahl, Cachetreffer und
Integritätsprüfung auseinanderhalten, danach einen wiederaufbaubaren Index
gegen denselben Datenbestand vergleichen.

KI-Unterstützung: Prüfstand, Tests und Dokumentation wurden mit Codex erstellt.
Die Messwerte stammen aus der ausgeführten synthetischen Probe; sie enthalten
keine menschlichen Urteile oder empirischen LLM-Ergebnisse.
