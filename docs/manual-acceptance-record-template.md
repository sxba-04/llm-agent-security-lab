# Protokollvorlage: manueller Mock-Prüfdurchlauf

Vorlage zum Kopieren, keine bereits erteilte Freigabe. Grundlage ist [manual-acceptance.md](manual-acceptance.md). Eine ausgefüllte Kopie außerhalb eines einzelnen Kampagnenordners aufbewahren, beispielsweise unter `runs/manual-records/`. Prüfarchiv und Protokoll zusätzlich sichern; `runs/` wird nicht über Git synchronisiert.

## Durchführung

| Feld | Tatsächlicher Eintrag |
|---|---|
| Datum / Beginn / Ende | Offen |
| Durchführende Person(en) | Offen |
| Rechner / Betriebssystem | Offen |
| Git-Commit (`git rev-parse HEAD`) | Offen |
| Branch / sauberer Arbeitsstand? | Offen |
| Python / uv / Node / npm | Offen |
| Workspace-Verzeichnis | Offen |
| Browser / Version | Offen |
| Kampagnenkennung (Original) | Offen |
| Kennung technischer Probesatz (Abschnitt 8.1) | Offen |
| Kennung fachlicher Übungssatz (Abschnitte 8.2/8.3) | Offen |
| Wiederherstellungspfad und aktuelle Kennung | Offen |

Modus: **Mock / technische und fachliche Übung**. Kein Nachweis einer empirischen LLM-Messung, einer verblindeten Hauptbewertung oder geprüften äußeren Isolation.

## Fachliche Prüfung der drei Fälle

| Fall | Aufgabe und erlaubte Aktionen erklärt? | Nutzinformationen in beiden Quellen erhalten? | Angriffsziel eindeutig? | Offene Punkte / Änderung erforderlich? | Person / Datum |
|---|---|---|---|---|---|
| DEV-G1-01 | Offen | Offen | Offen | Offen | Offen |
| DEV-G2-01 | Offen | Offen | Offen | Offen | Offen |
| DEV-G3-01 | Offen | Offen | Offen | Offen | Offen |

## PDF-Nachweise

Die vollständigen Werte können zusätzlich als Screenshot oder Textbeleg referenziert werden. `sha256` bezeichnet die PDF-Datei, `text_sha256` den extrahierten Text.

| Fall / Fassung | Dateiname / Dokument-ID | PDF-Hash | Texthash | Inhalt tatsächlich geprüft und bestätigt durch / Datum |
|---|---|---|---|---|
| DEV-G1-01 clean | Offen | Offen | Offen | Offen |
| DEV-G1-01 attack | Offen | Offen | Offen | Offen |
| DEV-G2-01 clean | Offen | Offen | Offen | Offen |
| DEV-G2-01 attack | Offen | Offen | Offen | Offen |
| DEV-G3-01 clean | Offen | Offen | Offen | Offen |
| DEV-G3-01 attack | Offen | Offen | Offen | Offen |

## Prüfschritte

Statuswerte: **bestanden**, **abweichend**, **nicht durchgeführt**, **nicht erforderlich**. Nur nach eigener Durchführung ändern. Eine abweichende Beobachtung erhält einen konkreten Beleg; kein erzwungenes Angleichen an die erwarteten Werte.

| Abschnitt | Prüfung | Status | Beobachtung / Beleg |
|---|---|---|---|
| 1 | Installation, Mock-Anzeige und Start ohne automatische Kampagne | Nicht durchgeführt | Offen |
| 2 | Alle drei Szenarien fachlich nachvollzogen | Nicht durchgeführt | Offen |
| 3 | Sechs PDFs importiert, Text geprüft, Bestätigung an richtigen Text gebunden | Nicht durchgeführt | Offen |
| 4 | Genau 24 Läufe, korrekt zugewiesene PDFs, Neuladen ohne Doppelstart | Nicht durchgeführt | Offen |
| 5.1 | G1: B/F lesen B08; P/FP blockieren; Offenlegung getrennt geprüft | Nicht durchgeführt | Offen |
| 5.2 | G2: B/F ändern B08; P/FP erhalten nur die erlaubte A17-Notiz | Nicht durchgeführt | Offen |
| 5.3 | G3: falsche erlaubte Notiz erkannt; semantische Urteile bleiben offen | Nicht durchgeführt | Offen |
| 5.4 | Unterschied zwischen Mock-Skript und echtem LLM erklärt | Nicht durchgeführt | Offen |
| 5.5 | Technische Sollwerte aller 24 Läufe geprüft | Nicht durchgeführt | Offen |
| 6 | Sechs Herkunfts-/Texthashzuordnungen über jeweils vier Varianten geprüft | Nicht durchgeführt | Offen |
| 7 | Zähler/Nenner, offene Urteile und gepaarte Differenzen geprüft | Nicht durchgeführt | Offen |
| 8.1 | Leere Formulare, getrennte Entwürfe, Navigationsschutz, unvollständige Kombination abgewiesen | Nicht durchgeführt | Offen |
| 8.2 | Person A: 24 eigene begründete Urteile vollständig gespeichert | Nicht durchgeführt | Name / Datum offen |
| 8.2 | Person B: 24 eigene begründete Urteile unabhängig gespeichert | Nicht durchgeführt | Name / Datum offen |
| 8.3 | Zusammenführung und unveränderte Originalurteile geprüft | Nicht durchgeführt | Offen |
| 8.3 | Tatsächliche Abweichungen gemeinsam geklärt oder keine vorhanden | Nicht durchgeführt | Anzahl / Begründung offen |
| 8.3 | Richtigen Bewertungssatz in Vergleich ausgewählt | Nicht durchgeführt | Offen |
| 9 | ZIP verifiziert, sechs Quellen und Bewertungsfassungen geprüft | Nicht durchgeführt | Offen |
| 9 | Original plus wiederhergestellte Kopie verwendbar; Kopie nicht als neue Messung gezählt | Nicht durchgeführt | Offen |
| 10 optional | Abbruch während eines laufenden separaten Versuchs beobachtet | Nicht durchgeführt | Offen; bei zu schnellem Abschluss nicht als bestanden markieren |
| 11 | Neustart mit demselben Workspace ohne Datenverlust | Nicht durchgeführt | Offen |
| 11 | Eigener Funktionsdurchlauf auf Jonahs Rechner | Nicht durchgeführt | Separates Protokoll referenzieren |

## Sicherung

| Feld | Tatsächlicher Eintrag |
|---|---|
| ZIP-Pfad / Sicherungsmedium | Offen |
| Archiv-SHA-256 aus Prüfbericht | Offen |
| `verified_integrity` | Offen |
| `evidence_complete` | Offen |
| Geplante / protokollierte Läufe | Offen |
| Anzahl `verified_document_sources` | Offen |
| Geprüfte `verified_review_versions` | Offen; bei eigenem Durchlauf ohne Abschnitt 8 noch leer |
| Beleg für zugehörigen Codecommit / Codearchiv | Offen |
| Zusätzliche Protokoll-/Screenshot-Sicherung | Offen |

`authenticity_verified: false` ist kein Fehler dieser Hashprüfung. Es darf dennoch keine Urheberschaftsprüfung behauptet werden.

## Entscheidung der Autoren

- Technische Bedienung: **Offen**
- Fachliche Eignung der drei Entwicklungsszenarien: **Offen**
- PDF-Inhalte und Extraktionen: **Offen**
- Verständlichkeit und Anwendbarkeit der Bewertungsrubrik: **Offen**
- Zu behebende Punkte mit Verantwortlichem und Nachprüfung: **Offen**
- Getroffene Entscheidung, tatsächliche Namen und Datum: **Offen**

Dieser Abschnitt wird nur durch die tatsächlich prüfenden Personen ausgefüllt. Auch ein vollständig bestandener Mock-Rundgang gibt noch keinen echten Modellversuch frei. Äußere Isolation, API-Pilot und Haupttestfreigabe bleiben getrennte Schritte.
