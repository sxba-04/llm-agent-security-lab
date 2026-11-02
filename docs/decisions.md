# Entscheidungsstand

Stand: 22. Oktober 2026. Die Angaben zur Abstimmung mit Ralf Brune und zur Arbeitsumgebung stammen aus den ausdrücklichen Rückmeldungen des Teams im Projektchat. Technische Vorschläge sind als solche gekennzeichnet.

| Entscheidung | Stand und Begründung |
|---|---|
| Fachlicher Umfang | Vom Team als durch Brune bestätigt gemeldet: Ticket-Assistent, indirekte Prompt Injection, B/F/P/FP |
| Sprache | Python vom Team angenommen; Anwendung und Auswertung werden in einer Sprache umgesetzt |
| Rechner | Windows-Firmenlaptop und privater Laptop bei Sebastian, privater Windows-Laptop bei Jonah; zusätzlich private PCs mit GPU |
| Modellbetrieb | API-Zugang vom Team angenommen; kein lokales Modell vorhanden |
| Budget | Höchstens 250 EUR für das gesamte Projekt; diese Grenze ist keine Freigabe für unbegrenzte Einzelaufrufe |
| Bedienung | Zunächst CLI, um Abläufe und Messung überschaubar zu halten |
| Datenhaltung | Synthetische JSON-Fälle und frischer Speicher pro Lauf |
| Abhängigkeiten | Anwendungskern mit Python-Standardbibliothek; gemeinsame Projektumgebung und Lockdatei |
| Entwicklung | Kontrolliertes Testmodell für technische Prüfungen; kein Ersatz für LLM-Pilot und Hauptmessung |
| Zusammenarbeit | Gemeinsames Repository; Änderungen über Branches und nachvollziehbare Reviews |
| Testtrennung | Zwölf Entwicklungspaare; finaler Katalog wird separat erstellt und vor Messung eingefroren |

## Noch vor dem echten Pilot festzulegen

1. API-Konto, konkretes toolfähiges Modell und dokumentierbarer Modellstand.
2. Aktuelle Preise, Umrechnung, Kostenreserve und erste kleine Pilotobergrenze.
3. Tatsächlich überprüfte Datei-, Netzwerk- und Ressourcengrenzen der Ausführungsumgebung.
4. Inhaltliche Prüfung der Entwicklungsfälle und der Bewertungsrubrik durch die Autoren.

## Noch vor der Hauptmessung festzulegen

1. Endgültiger Testkatalog und Fallzahl.
2. Filterregeln und genaue Reaktion auf jede Blockierung.
3. Modellparameter, Laufgrenzen und Umgang mit Infrastrukturfehlern.
4. Bewertungs- und Abgleichverfahren sowie Stichprobe zur Kontrolle automatisch bestimmter Ereignisse.
5. Eingefrorener Code-, Daten- und Konfigurationsstand mit vollständigem Manifest.

Neue Entscheidungen ergänzen Datum, Anlass, betrachtete Alternative, Begründung und betroffene Dateien. Frühere Entscheidungen werden bei Änderungen nicht stillschweigend überschrieben.

## Ergänzungen vom 23. Oktober 2026

| Entscheidung | Anlass, Alternative und Folge |
|---|---|
| FastAPI + React/TypeScript | Ausdrücklicher Wunsch des Teams nach Vergleich mit NiceGUI, Streamlit und PySide6. Die Oberfläche wird lokal betrieben; zusätzliche Python-/Node-Abhängigkeiten werden getrennt und mit Lockdateien festgehalten. Die frühere CLI-Entscheidung war der erste Entwicklungsstand, keine dauerhafte Begrenzung. |
| PDF-Wissensartikel | Ausdrückliche zusätzliche Entscheidung des Teams. Das Konzept schreibt kein Dateiformat vor. Textbasierte PDFs werden vor dem Versuch extrahiert, geprüft und als feste Quellen eingefroren; Tickets bleiben JSON. |
| Gemeinsamer Kern | CLI und HTTP-Dienst verwenden dieselben Ausführungs-, Policy- und Auswertungsfunktionen; React enthält keine zweite Sicherheitslogik. |
| Mock-Oberfläche | Der API-Pilot ist ausdrücklich vertagt. Die Webschnittstelle akzeptiert ausschließlich Mock-Aufträge; kein API-Schlüsselfeld und kein versteckter Modellwechsel. |
| Fachlich getrennte Nutzinformationen | Entwicklungsfälle enthalten Ticket- und Artikelfakten mit expliziter Herkunft. Der Verlust eines Artikels darf nicht systematisch bedeutungslos für die legitime Aufgabe sein. |
| PDF-Grenzen | Zunächst Text-PDFs, keine OCR, semantische Suche oder Bildanalyse. Extraktionsfehler werden getrennt von Prompt-Injection-Ergebnissen behandelt. |
| Serienverwaltung | Ein aktiver UI-Auftrag pro lokalem Dienst; expliziter Start, kooperativer Abbruch, dauerhaft gespeicherte Belege. |
| Merge-Verfahren | Abgeschlossene Tests und angeforderte Reviews auf dem aktuellen Commit, Befunde nachgeprüft. Keine Wiederholung des vorzeitigen Merge von PR #1. |

Die fachliche Abnahme der neuen Fälle und Bewertungsbeispiele durch Sebastian und Jonah sowie die äußere Isolation bleiben offen. Die technische Umsetzung fälscht hierfür keine Freigaben oder menschlichen Urteile.

## Ergänzungen vom 2. November 2026

Der folgende erste Stand wurde durch die weiter unten festgehaltenen Folgeentscheidungen zu Konten, Disk und Wiki ergänzt.

| Entscheidung / Einordnung | Anlass, Alternative und Folge |
|---|---|
| Bestehender kostenpflichtiger Render-Plan | Sebastian meldete das selbst vorgenommene Upgrade; die Render-Prüfung bestätigt `0.5c-512mb` mit 0,5 CPU und 512 MB RAM. Die frühere Beschränkung auf kostenlosen Compute ist damit für diesen bestehenden Dienst überholt. Zusätzliche Ressourcen sind dadurch nicht gebucht oder freigegeben. |
| Speicher bleibt zunächst flüchtig | Der laufende Dienst meldet weiterhin `ephemeral`; eine persistente Disk wurde nicht nachgewiesen. Das Compute-Upgrade ersetzt keine Speichereinrichtung. Die [Hosting-Anleitung](hosting.md) beschreibt einen möglichen Umstieg samt Sicherung und Neustartprüfung; eine tatsächliche Persistenzfreigabe und -prüfung bleiben offen. |
| Bestehendes Python-Layout beibehalten | `src/security_lab/` enthält bereits Backend, CLI und gemeinsamen Versuchskern. Eine pauschale Umbenennung in `backend/` bringt keinen fachlichen Vorteil. Künftige Aufteilungen sollen konkrete Modulkomplexität reduzieren und getrennt geprüft werden. |
| Dokumentation mit einem Einstieg bündeln | Codex ergänzt einen [Dokumentationsindex](README.md) und vorbereitete Wiki-Verweise. Die technischen Anleitungen bleiben im Repository versioniert; die Wiki-Dateien allein behaupten keine Veröffentlichung im getrennten GitHub-Wiki. |
| Betreiberzugang von Konten unterscheiden | Die vorhandenen zufälligen Codes bleiben ein gültiger Zugriffsschutz für das kleine Team. Ein persönlicher Konto-Login ist eine mögliche spätere Funktion, keine durch das Render-Upgrade automatisch eingerichtete Eigenschaft. Die Wiederherstellung eines verlorenen Codes erfolgt durch kontrollierte Rotation der Hashliste. |

Die betrieblichen Änderungen ändern weder den Variantenvergleich B/F/P/FP noch
menschliche Bewertungsregeln. Die Oberfläche bleibt auf Mock-Versuche begrenzt.
Ein Wechsel zu FastAPI Cloud wurde nicht vorgenommen; FastAPI bleibt das auf
Render betriebene Webframework.


## Weitere Entscheidungen vom 2. November 2026: Konten und Speicher

Diese ausdrücklichen Folgeentscheidungen ergänzen den oben dokumentierten früheren Stand.

| Entscheidung | Umsetzung und Grenze |
|---|---|
| Bestehenden Zugangscode behalten | Sebastian hat den Code wiedergefunden und sich erfolgreich angemeldet. Er war falsch eingegeben; eine Rotation ist nicht erforderlich. |
| GitHub-Login für beide Autoren | Optionaler OAuth-Ablauf mit State/PKCE, unveränderlicher Konto-ID-Freigabeliste und widerrufbaren eigenen Laborsitzungen implementiert. Keine Repository-/E-Mail-Berechtigungen, öffentliche Registrierung oder Passwortdatenbank. App-Registrierung, Backend-Konfiguration und Live-Anmeldung noch offen. |
| Dauerhaften Speicher einrichten | 1-GB-Disk am bestehenden Render-Dienst unter `/var/data` eingerichtet; Workspace `/var/data/security-lab`, nach erfolgreichem Neustartnachweis `persistent`. Kosten bei Einrichtung: 0,25 USD/Monat, genehmigte Obergrenze weiterhin 1 USD/Monat. Der alte Workspace enthielt keine regulären Dateien zur Migration. [Prüfstand](validation.md). |
| Wiki veröffentlichen | Startseite und Navigation wurden mit den versionierten Quellen veröffentlicht. Fachliche Anleitungen bleiben unter `docs/`; spätere Wiki-Aktualisierungen erfolgen bewusst und separat. |

Der GitHub-Login ändert den Betreiberzugang, nicht die Versuchssitzungsrechte oder
B/F/P/FP. Kontoidentität erzwingt weiterhin keine unabhängigen wissenschaftlichen
Bewertungen. Die Disk-Einrichtung und Neustartprüfung sind abgeschlossen; externe
Archivkopien bleiben erforderlich. Die produktive OAuth-Registrierung und echte
GitHub-Anmeldung stehen weiterhin aus.
