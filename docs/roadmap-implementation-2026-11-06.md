# Umsetzung der November-Roadmap

Ausgangspunkt: `079babd70eb38152c188fc71a355b8a19420c937`.
Änderungen: [PR #30](https://github.com/sxba-04/llm-agent-security-lab/pull/30).
Diese Seite dokumentiert technische Implementierung und konkrete Nachweise.
Fachliche Autorenfreigaben und empirische Modellversuche bleiben getrennt.

## Implementierte Pakete

| Paket | Ergebnis | Weitere Abnahme |
|---|---|---|
| 1 Qualität | Vorheriges Refactoring beibehalten; enger Ruff-Umfang E4/E9/F mit Lockdatei und CI; neue Befunde werden im PR geprüft | Aktuelle Sonar-/CodeQL-Analyse und Reviews am endgültigen Head |
| 2 Theme/Mobil | Hell/Dunkel/System, Start ohne hellen Zwischenzustand, semantische Farben, Druckpalette, größere Bedienelemente; Navigation, Tabs und Sitzungen mit Tastatur | Reale Bildschirmtastatur, Touch und Screenreader durch Anwender |
| 3 Browser | Begrenzte Chromium/Firefox/WebKit-Matrix, axe ohne pauschale Ausnahmen, mobile Kernabläufe, zwei visuelle Referenzen | CI-Ergebnis und visuelle Referenzen des aktuellen Heads |
| 4 Sicherung | Authentifizierter Gesamtdownload; originale PDFs, Belege, Bewertungen, Metadaten und verfügbare Git-Quellstände; strikte Prüfung und getrennte Wiederherstellung | Dauerhafter externer Ablageort, Verantwortlichkeit und regelmäßige Routine für Studienbelege |
| 5 Einrichtung | Nur lesende Diagnose mit Versionen, Build, Ports, Speicher, Rechten, Proxy-/CA-Hinweisen; Gesamtcheck und eindeutige IDE-Aufgaben | Frischer realer Windows-Klon bei Jonah |
| 6 Studienvorbereitung | Unveränderlicher Studienplan, vollständige Fallblöcke, Teilkampagnenverknüpfung, Hashprüfung und kostenbewusste Vorprüfung ohne Netzaufrufe | Autorenabnahme, äußere Isolation, reale Pilotfreigabe und danach Hauptmessung |
| 7 Zusammenarbeit | Versionierte Namen/Tags, gefilterter CSV-Export, erkennbare veraltete Bewertungen und unveränderte Originalhistorie | Eigenständige menschliche Urteile bleiben Verantwortung des Teams |
| 8 Leistung | Begrenzte reproduzierbare Messung mit Mock-Daten; reale Render-Basismetriken dokumentiert | Repräsentative Produktionslast; aktuell kein nachgewiesener Bedarf für SQLite oder mehr Compute |

Die Detailanleitungen stehen unter [Browser](browser-quality.md),
[Gesamtsicherung](workspace-backup.md), [Einrichtung](setup-windows.md),
[Studienmanifest](study-preflight.md), [Kampagnenorganisation](campaign-organization.md)
und [Ressourcenmessung](performance.md).

## Ausgangsprüfung und Datenerhalt

Am 6. November wurde die bestehende GitHub-Anmeldung von `sxba-04` im
Cloud-Browser erneut erfolgreich ausgeführt. Die Online-Werkbank enthielt einen
abgeschlossenen Mock-Versuch mit acht Läufen und keine importierten PDF-Quellen.
Das heruntergeladene Kampagnenarchiv bestand die Integritätsprüfung und wurde
in einen getrennten lokalen Ordner wiederhergestellt. Archiv-SHA-256:
`49711db709af17d521ec8030013b2b64d2780849fac61eb287ca4b0dd5c52322`.
Die Kampagnenrevision `6fcc07b4100c0454dbf102c1589e8f81dc4fadef` und der damalige
Live-Quellstand wurden zusätzlich als Git-Archive außerhalb des Dienstes bewahrt.
Dies war die Vorab-Sicherung mit dem bisherigen Kampagnenformat, keine Behauptung
eines damals schon vorhandenen vollständigen Workspace-Exports.

## Prüfnachweise

Die Baseline bestand unter Linux 337 Python-Tests mit einem erwarteten
Windows-spezifischen Skip. Der zuletzt lokal geprüfte Stand bestand
417 Python-Tests (ein Windows-spezifischer Skip), 107 React-Tests, Ruff und den
Produktionsbuild mit Python 3.12.14, Node 24 und den Lockdateien. Nach den dabei
gefundenen Bedienkorrekturen bestanden über die gezielten Nachläufe alle 13
funktionalen lokalen Firefox-Fälle und sechs HTTPS-Fälle. Chromium konnte in
dieser lokalen Umgebung nicht starten, WebKit fehlen Systembibliotheken.
GitHub-CI führt die vorgesehenen Windows-/Linux- und Browserprüfungen aus.
Maßgeblich für die Veröffentlichung sind sämtliche Pflichtprüfungen und Reviews
am endgültigen Head von PR #30; die hier genannten Entwicklungsprüfungen
ersetzen diesen Nachweis nicht. Ein laufender, fehlgeschlagener oder
übersprungener Check wird nicht als bestanden gezählt.
Die abschließenden CI-, Review-, Deployment- und Wiederherstellungsnachweise
werden mit ihren jeweiligen Commit- und Lauf-IDs im verlinkten PR #30 festgehalten.

Die unabhängigen Gegenprüfungen korrigierten vor der Veröffentlichung beschädigte
Sicherungsinventare, konkurrierende Restore-Ziele, temporäre Metadatenpublikation,
ungültige Unicode-Metadaten und unzureichend validierte Studien-Provenienz.
Die zugehörigen Regressionstests erhalten diese Fehlergrenzen. Die unabhängige
Integration prüfte außerdem API-/Sperrinteraktionen, Studienprovenienz,
Bewertungsrevisionen und den Versionsübergang. Der lokale Gesamtcheck reicht
seine Installationssperre auch an den von Playwright gestarteten Backendprozess
weiter; dies wurde separat mit einem instrumentierten Unterprozess geprüft.
Bekannte Metadaten-Schreibreste nach einem harten Prozessabbruch bleiben mit
sichtbarer Warnung und Originalbytes exportierbar. Die historischen technischen
Persistenzbelege werden getrennt von wissenschaftlichen Kampagnen gesichert.
Die abschließende Backup-Prüfung erhält auch ältere Kampagnen namens `exports`
und verschachtelte Belegdateien mit der Endung `.lock`. Ungültige Manifesttypen
werden abgelehnt; ein Vergleich der Kampagneninventare vor und nach der
Archivprüfung verhindert die Veröffentlichung bei einer ausgelassenen Kampagne.
Der [Release- und Rollback-Ablauf](release-rollback.md) beschreibt die
Vorab-Sicherung, getrennte Pages-/Render-Kontrolle und einen geordneten Rückweg.

## Qualitätsdienste

Das zuletzt verfügbare Sonar-Inventar für die Baseline nennt fünf offene
Bestandsmeldungen, Quality Gate OK, 88,8 % Gesamtabdeckung und 92,1 % auf neuem
Code. Quelle: [Workflow 41640497436](https://github.com/sxba-04/llm-agent-security-lab/actions/runs/41640497436),
Artefakt `13233890699`, Analyse `cd937562-c5fe-4599-8cbb-5a26382eff35`.
Die fünf dokumentierten Verwendungen betreffen Hosted-Bindung, Legacy-
beforeunload, UTF-8-Validierung, reproduzierbare Zufallsreihenfolge und sicheren
TLS-Standardkontext. Regeln und Quality Gate wurden nicht abgeschaltet.
Der direkte Sonar-Zugang lieferte in dieser Sitzung einen CloudFront-Fehler;
die GitHub-Analyseartefakte bleiben auswertbar.

Die erste vollständige PR-Analyse auf `6b48f567` meldete 45 Annotationen,
darunter Sicherheitsmeldungen mit behaupteter LLM-gesteuerter CLI-Eingabe.
Die einzelnen tatsächlichen Datenflüsse wurden erneut geprüft; der Modellkern
stellt ausschließlich die beiden synthetischen Ticket-Tools bereit. Konkrete
Einordnungen stehen unter [Backup/Archivpfade](sonar-triage/pr30-backup-cli.md),
[Studien-/Scanner-CLI](sonar-triage/pr30-study-cli.md),
[Portdiagnose](sonar-triage/doctor-pr30.md) und
[Frontend-Semantik](sonar-triage/pr30-frontend.md).
Diese Quellprüfungen sind keine Behauptung eines bereits bestandenen erneuten
Quality Gates. Berechtigte Wartbarkeitshinweise wurden korrigiert; notwendige
Tastaturfokussierung bleibt erhalten. OAuth-Ziele werden nach strikter Prüfung
aus der festen GitHub-Adresse aufgebaut, doppelte OAuth-Parameter abgelehnt.
Der Inventarparser erhält fehlende Werte und Periodenangaben ausdrücklich,
statt fehlende Messungen als null auszugeben.

Eine spätere Browserprüfung fand beim Wechsel des aktiven Navigationslinks
einen Kontrastverlust während der Farbübergänge. Ein gezielter Browsertest
reproduzierte den Fehler in beiden Themes an Zwischenständen. Text und
Hintergrund der Navigation wechseln deshalb jetzt gemeinsam ohne Farbinterpolation.
Die Farbauswahl und die übrigen Animationen bleiben erhalten; axe wird weiterhin
ohne Ausnahme für diese Elemente ausgeführt.

Der zusätzliche [GitHub-AI-Scan vom 4. November](https://github.com/sxba-04/llm-agent-security-lab/actions/runs/41799108962)
scheiterte wegen ausgeschöpfter monatlicher Copilot-Quote. Das ist weder ein
bestandener Scan noch ein gemeldeter Sicherheitsfehler. Die vorhandene
Copilot-Ausnahme bleibt begrenzt; aktuelle Codex-Code-/Security-Reviews,
unabhängige Gegenprüfung und Pflichtprüfungen sind vor dem Merge erforderlich.

## Wissenschaftliche Grenzen

Der Ausführungskern, B/F/P/FP und die gemeinsame Auswertung bleiben unverändert.
Webversuche sind Mock-only. Der Studienplan kann 720 Läufe in 480 und 240
verknüpfen, ohne das UI-Limit zu erhöhen oder die komplette Reihenfolge eines
monolithischen Laufs zu behaupten; die Teilseeds sind explizit eingefroren.
Kostenangaben sind konfigurierte Schätzungen, keine Preisprüfung oder
Provider-Rechnungsobergrenze. Eine Datei mit einer Freigabe ist nur ein
referenzierter Beleg und wird nicht automatisch als echte Freigabe zertifiziert.
