# Review-Einstellungen und Übergaben

Die Konfigurationsempfehlungen stammen vom 29. Oktober 2026. Sebastian hat ihre Umsetzung zurückgemeldet. Der Abschnitt zum Review-Ablauf wurde am 9. November 2026 anhand der PR-Verläufe aktualisiert.

## Drei getrennte Nachweise

GitHub Actions führt die Tests aus. Codex Code Review prüft Änderungen allgemein, Codex Security Review untersucht zusätzlich Sicherheitsfragen. GitHub Copilot ist ein weiterer Reviewer mit eigener Abrechnung und eigenem Kontingent. Ein fehlgeschlagener Job wegen Kontingent oder Berechtigung ist weder ein bestandener Review noch ein Sicherheitsbefund.

Bei PR #3 war das normale Codex-Review erfolgreich. Die ursprüngliche Sicherheitsprüfung meldete dagegen ausdrücklich, dass die gesonderte Freigabe **Use credits for security reviews** benötigt wird. Nach der vom Nutzer gemeldeten Aktivierung konnten am 27.10. beide Codex-Prüfungen auf `186ca6d` ohne Befunde abgeschlossen werden. Copilot blieb wegen seines eigenen Kontingents nicht verfügbar. Die bereits ausdrücklich genehmigte Copilot-Ausnahme wurde dokumentiert.

Credits sind Abrechnungseinheiten; Tokens sind verarbeitete Informationseinheiten. Entwicklungs-/Review-Credits sind vom Budget der späteren Modell-API-Versuche zu trennen. Der gleiche Account synchronisiert keine uncommitteten Dateien, lokalen Kampagnen oder IDE-Einstellungen. Die Modellwahl im lokalen Codex ist kein Nachweis des von einem GitHub-Review verwendeten Modells.

## Empfohlene Konfiguration

| Einstellung | Empfehlung und Zweck |
|---|---|
| Automatisches Codex Code Review | Aktiviert lassen; beim Öffnen beziehungsweise Bereitstellen eines PRs starten. |
| Nach Korrekturen | Änderungen bündeln und für den endgültigen Commit den Stand beider Reviews prüfen. Ob ein weiterer Push automatisch einen Lauf startet, hängt von den Einstellungen ab. |
| Vollständiger Code Review | Gezielter Einsatz bei größeren Umbauten und vor einem Meilenstein; keine Zusage vollständiger Fehlerfreiheit. |
| Automatische Security Reviews | Aktiviert lassen, gemeinsam mit Code Review auslösen. |
| Security-Meldeschwelle | Für dieses Labor automatisch und manuell **Medium** erwägen. Das steuert veröffentlichte Befunde, nicht die Prüftiefe. Den Status und gegebenenfalls vollständigen Bericht prüfen. |
| Threat-Model-Pfad | Nach Aufnahme ins Repository ausdrücklich `docs/threat-model.md` konfigurieren; grauer Platzhaltertext allein bestätigt keine gespeicherte Einstellung. |
| Reviews für beide Autoren | **All PRs** erwägen, wenn der zahlende Account die Prüfungen auch für Jonahs PRs übernehmen soll. |
| Copilot-Aufwand | **Balanced** beibehalten; eine ausgeschöpfte Quote nicht durch wiederholte identische Anforderungen belasten. |

Die wichtigsten dauerhaften Review-Regeln stehen in `AGENTS.md` unter **Code Review Rules**. Die root `SECURITY.md` beschreibt Sicherheitsmaßstab und Grenzen; das Threat Model beschreibt die konkreten Datenübergänge. Diese Dateien ersetzen keine Tests oder abgeschlossenen Reviews.

## Repository-Regeln

Das am 29. Oktober 2026 aktivierte Ruleset „Protect main“ verlangt am 9. November sieben Statusprüfungen, einen Pull Request auf aktuellem Basisstand und erledigte Review-Gespräche. Force-Push und Löschen sind gesperrt, die Bypass-Liste ist leer. Die vereinbarte inhaltliche Review-Pflicht gilt zusätzlich. [Aktives Ruleset](https://github.com/sxba-04/llm-agent-security-lab/rules/26123924) · [Branchschutz-Dokumentation](branch-protection.md)

## Automatische Reviews abwarten

Einen prüffertigen PR direkt zur Prüfung öffnen. Bei laufender Arbeit die Änderungen im Draft bündeln und den fertigen Stand auf **Ready for review** setzen. Im **Codex Review Summary** für Code Review und Security Review jeweils Commit, Status und **Review trigger** mit dem aktuellen PR-Stand abgleichen. Einen bereits eingeplanten oder laufenden Review bis zum Abschluss verfolgen. Nach einem weiteren Push den Abgleich für den neuen Commit wiederholen.

In PR #21 meldete Codex für beide Prüfungen **PR opened**. In PR #30 war der finale Commit `00de369` am 6. November um 10:24 UTC bereit. Beide Prüfungen endeten um 10:28 UTC mit dem Auslöser **Draft marked ready**. [Review-Nachweis #21](https://github.com/sxba-04/llm-agent-security-lab/pull/21#issuecomment-6566506902) · [Review-Nachweis #30](https://github.com/sxba-04/llm-agent-security-lab/pull/30#issuecomment-6680850426)

## Manueller Neustart

Fehlt nach der Aktualisierung des Summary ein benötigter Review für den aktuellen Commit, kann er einmal gezielt in der PR-Diskussion angefordert werden. `@codex review` startet den Code-Review, `@codex security review` den Sicherheitsreview. Bei gekoppelten Prüfungen zuerst den Status beider Zeilen nach dem Start des Code-Reviews prüfen. Copilot wird über die Reviewer-Auswahl erneut angefordert.

Den jeweiligen Befehl als eigenen Kommentar ohne zusätzlichen Erläuterungstext senden und danach im **Codex Review Summary** prüfen, welcher Review tatsächlich für welchen Commit gestartet wurde. Bei PR #5 aktualisierten kommentierte Security-Anforderungen zunächst nur den Code-Review; erst der alleinstehende Security-Befehl startete nachweislich den Security-Review am aktuellen Head. Ein abgeschlossener Code-Review ist kein Ersatz für dessen Security-Status.

Vor dem Merge die tatsächlich geprüfte Commit-ID vergleichen. Nach einer Korrektur gilt der vorherige Review nicht automatisch für den neuen Code. Kontingentausfälle und ausdrücklich genehmigte Ausnahmen werden im PR nachvollziehbar festgehalten; siehe [Arbeitsablauf](workflow.md).

## Offizielle Referenzen

- [Codex GitHub-Integration und AGENTS-Regeln](https://learn.chatgpt.com/docs/third-party/github)
- [Codex Security Review, Auslösung und Meldeschwellen](https://learn.chatgpt.com/docs/security/security-review)
- [Tokens und Credits](https://learn.chatgpt.com/docs/pricing)
- [GitHub Copilot Code Review konfigurieren](https://docs.github.com/en/copilot/how-tos/copilot-on-github/set-up-copilot/configure-code-review)

Diese Referenzen wurden am 27.10.2026 geprüft. Verfügbare Schalter, Kontingente und Abrechnung können sich ändern; maßgeblich sind der aktuelle Accountstatus und der tatsächliche Jobbericht.
