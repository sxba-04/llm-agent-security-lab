# Technischer Prüfstand vom 22. Oktober 2026

Die folgenden Prüfungen betreffen die Implementierung. Sie sind keine empirischen Ergebnisse über die Angreifbarkeit eines Sprachmodells.

## Lokal ausgeführte Prüfungen

- Python 3.12.14 unter Linux; Installation mit `uv sync --locked` erfolgreich.
- 104 automatisierte Tests mit `uv run --locked python -m unittest discover -s tests -q` erfolgreich.
- Alle zwölf Entwicklungspaare strukturell validiert.
- Demo mit 24 von 24 abgeschlossenen Mock-Läufen.
- Vollständiger Entwicklungskatalog: zwölf Paare, vier Varianten, zwei Quellfassungen und drei Wiederholungen ergeben 288 von 288 abgeschlossene Mock-Läufe.
- Zusammenfassung aus hashgeprüften Originalläufen neu berechnet und als CSV exportiert.
- Export, Import und Anwendung zweier synthetischer Testbewertungen im automatisierten Integrationstest geprüft. Es wurden keine menschlichen wissenschaftlichen Bewertungen erfunden.
- Python-Module kompiliert; lokale Dokumentationsverweise geprüft.

## Gegenprüfung

Ein unabhängiger technischer Review identifizierte Lücken bei der Verbindung menschlicher Urteile mit der Zusammenfassung, der Erkennung wechselnder API-Modellkennungen, der Erhaltung von Belegen bei Fehlern nach einer API-Antwort und der Bewertung unklarer Fehlblockierungen. Die Implementierung und zugehörige Tests wurden entsprechend ergänzt.

GitHub Actions ist für Windows und Linux vorbereitet. Der tatsächliche Status der jeweiligen Commit-Prüfung ist im zugehörigen Actions-Lauf sichtbar; ein lokaler Linux-Test allein belegt noch keine erfolgreiche Windows-Ausführung.

## Noch ausstehend

- Test auf den konkreten Rechnern des Teams einschließlich Firmenproxy.
- Eingerichtete und überprüfte äußere Isolation für echte Angriffsversuche.
- Auswahl und dokumentierte Preisprüfung eines konkreten API-Modells.
- Erster echter API-Aufruf und Pilot mit tatsächlich beobachtetem Modellverhalten.
- Unabhängige menschliche Bewertung, Entwicklung des getrennten Haupttestkatalogs, Einfrieren und Hauptmessung.

Der API-Adapter wurde mit simulierten Transportantworten geprüft. Es wurden keine echten API-Anfragen ausgeführt und keine Modellkosten verursacht. Budgetreservierungen sind lokale konservative Schätzungen auf Basis konfigurierter Preise, keine Zusage des Modellanbieters über einen absoluten Rechnungsbetrag.
