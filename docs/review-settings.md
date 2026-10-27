# Review-Einstellungen und Übergaben

Stand: 27. Oktober 2026. Empfehlungen für dieses Repository; Kontoeinstellungen wurden dadurch nicht verändert.

## Drei getrennte Nachweise

GitHub Actions führt die Tests aus. Codex Code Review prüft Änderungen allgemein, Codex Security Review untersucht zusätzlich Sicherheitsfragen. GitHub Copilot ist ein weiterer Reviewer mit eigener Abrechnung und eigenem Kontingent. Ein fehlgeschlagener Job wegen Kontingent oder Berechtigung ist weder ein bestandener Review noch ein Sicherheitsbefund.

Bei PR #3 war das normale Codex-Review erfolgreich. Die ursprüngliche Sicherheitsprüfung meldete dagegen ausdrücklich, dass die gesonderte Freigabe **Use credits for security reviews** benötigt wird. Nach der vom Nutzer gemeldeten Aktivierung konnten am 27.10. beide Codex-Prüfungen auf `186ca6d` ohne Befunde abgeschlossen werden. Copilot blieb wegen seines eigenen Kontingents nicht verfügbar. Die bereits ausdrücklich genehmigte Copilot-Ausnahme wurde dokumentiert.

Credits sind Abrechnungseinheiten; Tokens sind verarbeitete Informationseinheiten. Entwicklungs-/Review-Credits sind vom Budget der späteren Modell-API-Versuche zu trennen. Der gleiche Account synchronisiert keine uncommitteten Dateien, lokalen Kampagnen oder IDE-Einstellungen. Die Modellwahl im lokalen Codex ist kein Nachweis des von einem GitHub-Review verwendeten Modells.

## Empfohlene Konfiguration

| Einstellung | Empfehlung und Zweck |
|---|---|
| Automatisches Codex Code Review | Aktiviert lassen; beim Öffnen beziehungsweise Bereitstellen eines PRs starten. |
| Nach Korrekturen | Änderungen bündeln und vor dem Merge auf dem endgültigen Commit erneut anfordern. Reviews bei jedem Push sind eine mögliche Alternative mit höherem Verbrauch. |
| Vollständiger Code Review | Gezielter Einsatz bei größeren Umbauten und vor einem Meilenstein; keine Zusage vollständiger Fehlerfreiheit. |
| Automatische Security Reviews | Aktiviert lassen, gemeinsam mit Code Review auslösen. |
| Security-Meldeschwelle | Für dieses Labor automatisch und manuell **Medium** erwägen. Das steuert veröffentlichte Befunde, nicht die Prüftiefe. Den Status und gegebenenfalls vollständigen Bericht prüfen. |
| Threat-Model-Pfad | Nach Aufnahme ins Repository ausdrücklich `docs/threat-model.md` konfigurieren; grauer Platzhaltertext allein bestätigt keine gespeicherte Einstellung. |
| Reviews für beide Autoren | **All PRs** erwägen, wenn der zahlende Account die Prüfungen auch für Jonahs PRs übernehmen soll. |
| Copilot-Aufwand | **Balanced** beibehalten; eine ausgeschöpfte Quote nicht durch wiederholte identische Anforderungen belasten. |

Die wichtigsten dauerhaften Review-Regeln stehen in `AGENTS.md` unter **Code Review Rules**. Die root `SECURITY.md` beschreibt Sicherheitsmaßstab und Grenzen; das Threat Model beschreibt die konkreten Datenübergänge. Diese Dateien ersetzen keine Tests oder abgeschlossenen Reviews.

## Repository-Regeln

Die GitHub-Branchabfrage meldete `main` am 27.10.2026 als nicht geschützt (`protected: false`). Wenn der Tarif die benötigten Regeln für dieses private Repository erlaubt, sollten Pull Requests und erfolgreiche Windows-/Linux-Prüfungen vor dem Merge technisch verlangt und Force-Pushes verhindert werden. Kontingentabhängige Bot-Prüfungen müssen dabei zur ausdrücklich vereinbarten Ausnahme passen. Diese Runde hat keine administrativen Branch- oder Kontoeinstellungen geändert.

## Manueller Neustart

In der PR-Diskussion kann `@codex review` einen neuen Code-Review und `@codex security review` einen neuen Sicherheitsreview anfordern. Wenn automatische Sicherheitsreviews bereits an Code-Reviews gekoppelt sind, zuerst prüfen, ob der Sicherheitsjob gestartet wurde; keinen zusätzlichen doppelten Lauf erzeugen. Copilot wird über die Reviewer-Auswahl erneut angefordert.

Vor dem Merge die tatsächlich geprüfte Commit-ID vergleichen. Nach einer Korrektur gilt der vorherige Review nicht automatisch für den neuen Code. Kontingentausfälle und ausdrücklich genehmigte Ausnahmen werden im PR nachvollziehbar festgehalten; siehe [Arbeitsablauf](workflow.md).

## Offizielle Referenzen

- [Codex GitHub-Integration und AGENTS-Regeln](https://learn.chatgpt.com/docs/third-party/github)
- [Codex Security Review, Auslösung und Meldeschwellen](https://learn.chatgpt.com/docs/security/security-review)
- [Tokens und Credits](https://learn.chatgpt.com/docs/pricing)
- [GitHub Copilot Code Review konfigurieren](https://docs.github.com/en/copilot/how-tos/copilot-on-github/set-up-copilot/configure-code-review)

Diese Referenzen wurden am 27.10.2026 geprüft. Verfügbare Schalter, Kontingente und Abrechnung können sich ändern; maßgeblich sind der aktuelle Accountstatus und der tatsächliche Jobbericht.
