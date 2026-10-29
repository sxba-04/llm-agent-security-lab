# Beiträge und KI-Unterstützung

Die Studienarbeit wird von Sebastian Herrmann und Jonah Häuser verantwortet. Eine technische Aufgabenübernahme durch ChatGPT/Codex ersetzt weder die eigenständige Prüfung noch die Erklärung der verwendeten Methode und Implementierung.

## Dokumentierter Ausgangsstand

| Datum | Beitrag | Herkunft | Prüfstatus |
|---|---|---|---|
| 22.10.2026 | Bestätigung der Betreuerfreigabe, Arbeitsgeräte, API-Budget und Python-Wahl | Rückmeldung des Teams im Projektchat | Als Eingabe für den Projektstart übernommen |
| 22.10.2026 | Erster Implementierungsentwurf, Entwicklungsfälle, technische Tests und Projektdokumentation | ChatGPT/Codex mit parallelen Teilaufgaben | Technische Prüfungen im Implementierungsprozess; menschliches Review durch die Autoren steht aus |
| 23.10.2026 | Einrichtung auf dem LUBW-Laptop, Git/uv/Python und 104 erfolgreiche Tests | Rückmeldung und Screenshots von Sebastian; Einrichtung mit lokalem Codex | Vom Nutzer als erfolgreich gemeldet; keine Behauptung einer bereits geprüften äußeren Isolation |
| 23.10.2026 | Auswahl FastAPI/React und PDF-Artikelimport, Zustimmung zur abgeschlossenen Review-Prüfung vor Merge | Ausdrückliche Entscheidung des Teams im Projektchat | In Implementierung und Projektregeln übernommen |
| 23.10.2026 | Review-Korrekturen, Quellenzuordnung, Vergleichsauswertung, Weboberfläche, PDF-Verarbeitung und Archive | ChatGPT/Codex mit paralleler Implementierung und unabhängigen technischen Gegenprüfungen | Technischer Prüfstand siehe validation.md; fachliche Freigabe der Fälle und echte menschliche Bewertungen stehen aus |
| 23.10.2026 | Korrektur vorübergehender Windows-Dateisperren beim atomaren Speichern von Laufbelegen und fünf Regressionstests | Lokaler Codex nach reproduziertem WinError 5 beim parallelen Lesen der Oberfläche | 230 Python-Tests und beide echten Browsertests lokal bestanden; unabhängige technische Gegenprüfung ohne Befund; menschliches Review steht aus |
| 27.10.2026 | Abschluss PR #3, Repository-Prüfung, Fehlerkorrekturen an Speicherung/PDF/Bewertungen/Auswertung, Windows-Browser-CI sowie Review- und Sicherheitsdokumentation | ChatGPT/Codex mit parallelen Quellcodeprüfungen und unabhängiger technischer Gegenprüfung | Umfang siehe repository-audit-2026-10-27.md; tatsächlicher Teststand siehe validation.md; fachliche und menschliche Freigaben bleiben bei den Autoren |
| 29.10.2026 | Gemeinsame VS-Code-Aufgaben, Trennung persönlicher Einstellungen und Korrektur der Windows-Aufrufe mit npm.cmd | Lokaler Codex mit paralleler Dokumentationsarbeit und unabhängiger technischer Gegenprüfung | 254 Python-, 22 React- und zwei echte Browsertests unter Windows bestanden; frische Projektkopie mit Leerzeichen im Pfad geprüft; Grenzen und Details siehe validation.md |

Diese Tabelle behauptet nicht, dass die Autoren den generierten Code bereits selbst geschrieben, vollständig geprüft oder empirisch validiert haben. Der tatsächliche Prüfstand wird nach dem Review ergänzt.

## Einträge für eigene Arbeit

Für relevante Beiträge werden Verantwortliche, konkrete Tätigkeit, Gegenprüfung und Bezug zu PR, Commit oder Kapitel festgehalten. Ein geeigneter Eintrag lautet beispielsweise:

| Datum | Person | Konkrete Eigenleistung | Gegenprüfung | Nachweis |
|---|---|---|---|---|
| Auszufüllen | Auszufüllen | Beispielsweise Policyregel begründet, Grenzfall ergänzt und Ergebnis erläutert | Auszufüllen | PR oder Commit und gegebenenfalls Kapitel |

Anzahl der Commits und Codezeilen sind kein Ersatz für die fachliche Beschreibung. Gemeinsame Tätigkeiten werden mit den jeweiligen Anteilen erläutert.

## Umgang mit KI-generierten Bestandteilen

- Übernommenen Code und die zugehörigen Sicherheitsannahmen lesen und erklären können.
- Fallformulierungen, korrekte Fakten und Angriffsziele eigenständig prüfen.
- Technische Testergebnisse von empirischen LLM-Ergebnissen unterscheiden.
- Quellen vor Verwendung im Manuskript selbst lesen und prüfen.
- Weitere KI-Nutzung mit Werkzeug, Zweck und betroffenen Teilen ergänzen.

Der spätere KI-Nachweis der Arbeit beschreibt die tatsächlich erfolgte Nutzung. Diese Projektdokumentation unterstützt ihn, ersetzt aber nicht die nach den Hochschulvorgaben erforderliche Erklärung.
