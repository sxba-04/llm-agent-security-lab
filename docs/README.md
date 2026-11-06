# Projektdokumentation

Die Dokumentation gehört zum Code und wird gemeinsam mit Änderungen über Pull Requests geprüft. Für den Einstieg reichen die folgenden Wege; historische Prüfberichte sind zusätzlich verlinkt, ersetzen aber keine aktuellen CI- oder Anbieterprüfungen.

## Ich möchte …

| Ziel | Einstieg |
|---|---|
| Die Anwendung online verwenden oder den Zugang erneuern | [Hosting, Anmeldung und Speicher](hosting.md), [GitHub-Login und Sitzungen](github-login.md) |
| Die Anwendung lokal installieren und starten | [Windows-Einrichtung](setup-windows.md), [VS-Code-Aufgaben](vscode.md) |
| Fälle, PDFs, Kampagnen und Bewertungen bedienen | [Werkbank](workbench.md), [PDF-Quellen](pdf-sources.md) |
| Daten sichern und wiederherstellen | [Vollständige Workspace-Sicherung](workspace-backup.md), [Kampagnenarchive](archives.md) |
| Die erste gemeinsame Abnahme durchführen | [Klickanleitung](manual-acceptance.md), [leeres Prüfprotokoll](manual-acceptance-record-template.md) |
| Den Aufbau und die Ordner verstehen | [Architektur und Modulgrenzen](architecture.md) |
| Die Versuche und ihre Aussagegrenzen verstehen | [Versuchsablauf und Bewertung](experiment.md) |
| Einen echten Modellpilot vorbereiten | [Studienmanifest und Vorprüfung](study-preflight.md), [Modellzugang und Budget](api.md), [offene Entscheidungen](decisions.md) |
| Browser, Mobilansicht und Themes prüfen | [Browser- und Barrierefreiheitstests](browser-quality.md) |
| Langsame Abläufe oder Speicherbedarf untersuchen | [Begrenzte Ressourcenmessung](performance.md) |
| Eine Änderung beitragen oder einen Fehler beheben | [CONTRIBUTING](../CONTRIBUTING.md), [Arbeitsablauf](workflow.md), [Projektanweisungen](../AGENTS.md) |
| Tests und Sicherheitsbefunde nachvollziehen | [Qualitätswerkzeuge](quality-tooling.md), [GitHub Actions](github-actions.md), [Validierungsnachweise](validation.md) |
| Weitere Verbesserungen priorisieren | [Ausbauplan für Oberfläche, Tests, Betrieb und Datenhaltung](roadmap-2026-11.md) |
| Sicherheitsgrenzen oder Review-Anforderungen prüfen | [Security Policy](../SECURITY.md), [Bedrohungsmodell](threat-model.md), [Reviews](review-settings.md), [Branchschutz](branch-protection.md) |
| Entscheidungen und KI-Unterstützung nachverfolgen | [Entscheidungen](decisions.md), [Beiträge](contributions.md) |

## Qualität und historische Nachweise

- [Sonar-Inventur erzeugen und lesen](sonar-inventory.md)
- [Sonar-Triage des damaligen Inventars](sonar-triage/README.md)
- [CodeQL-Triage vom 1. November 2026](codeql-triage-2026-11-01.md)
- [Repository-Prüfung vom 27. Oktober 2026](repository-audit-2026-10-27.md)

Ein grünes Quality Gate bewertet die konfigurierten Kriterien; es bedeutet nicht automatisch null Befunde im gesamten Bestand. Ebenso sind Mock-Tests technische Nachweise und keine empirischen LLM-Ergebnisse. Für eine aktuelle Bewertung stets Datum und Commit des Berichts prüfen.

## Wiki und Pflege

Ein GitHub-Wiki eignet sich als kurze Startseite für Sebastian, Jonah und den Betreuer. Die verbindlichen technischen Anleitungen bleiben hier im Repository, damit sie mit Codeänderungen versioniert und geprüft werden. Eine zweite vollständige Kopie der Dokumentation würde leicht veralten.

Die Startseite und Navigation wurden am 2. November 2026 im [GitHub-Wiki](https://github.com/sxba-04/llm-agent-security-lab/wiki) veröffentlicht. Ihre [versionierten Quellen](wiki/README.md) bleiben hier. Weitere Änderungen zuerst im Repository prüfen und anschließend bewusst ins separate Wiki übernehmen; ein Repository-Merge synchronisiert es nicht automatisch.

Bei fachlich relevanten Änderungen werden die betroffenen Anleitungen, der Entscheidungsstand und die Beiträge mitgepflegt. Versuchsfreigaben, menschliche Bewertungen und erfolgreiche Tests werden nur dokumentiert, wenn sie tatsächlich stattgefunden haben.

- [Qualitätskorrekturen vom 3. November 2026](quality-improvements-2026-11-03.md): Refactoring, Sonar-Dispositionen und Prüfnachweise.
