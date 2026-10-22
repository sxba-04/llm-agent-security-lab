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
