# Schutz des Hauptbranches

Am **29. Oktober 2026** wurde [Protect main, Ruleset 26123924](https://github.com/sxba-04/llm-agent-security-lab/rules/26123924) tatsächlich aktiviert. Anschließend wurden die gespeicherte Regel samt Ziel `refs/heads/main`, allen vier Checks und leerer Bypass-Liste sowie `protected: true` über GitHub geprüft. `current_user_can_bypass` lautet `never`.

Die Konfiguration ist als [importierbares Ruleset](../configs/github-main-ruleset.json) versioniert. **Eine JSON-Datei im Repository aktiviert allein keinen Schutz.** Die folgenden Einrichtungsschritte dienen der nachvollziehbaren Wiederherstellung; die bereits aktive Regel nicht doppelt anlegen.

## Aktivierter Zustand

| Regel | Einstellung |
|---|---|
| Ziel | Ausschließlich `refs/heads/main` |
| Enforcement | Active |
| Änderungen | Pull Request erforderlich |
| Pflichtprüfungen | `test (ubuntu-latest)`, `test (windows-latest)`, `frontend (ubuntu-latest)`, `frontend (windows-latest)` |
| Herkunft der Checks | GitHub Actions, App-ID 15368; im Repository tatsächlich geprüft |
| Aktueller Basisstand | Vor dem Merge erforderlich |
| Offene Review-Gespräche | Müssen erledigt sein |
| Force-Push und Löschen | Verboten |
| Umgehung | Keine Bypass-Liste, auch keine pauschale Ausnahme für Administratoren |

Es werden null zusätzliche formale **Approvals** verlangt. Damit bleibt der ausdrücklich vereinbarte Ablauf mit Codex-Prüfungen und anschließendem Merge von PRs aus demselben Nutzerkonto möglich. Ein Codex-Kommentar ist nicht automatisch ein GitHub-Approval. Das ersetzt weder die in [AGENTS.md](../AGENTS.md) vorgeschriebenen aktuellen Code-/Security-Reviews noch die fachliche Prüfung durch die Autoren. Copilot wird wegen der ausdrücklich genehmigten Kontingentausnahme nicht als harter Pflichtcheck eingetragen. Falls das Team später verpflichtende menschliche Freigaben möchte, gemeinsam eine Approval-Zahl von mindestens eins festlegen.

## Einrichtung mit der GitHub-Oberfläche

1. Repository öffnen, **Settings → Rules → Rulesets** auswählen.
2. Zuerst bestehende Regeln prüfen. Eine bereits passende Regel nicht doppelt anlegen.
3. Unter **New ruleset** die Funktion **Import a ruleset** wählen und `configs/github-main-ruleset.json` hochladen. Alternativ **New branch ruleset** wählen und die obige Tabelle manuell übernehmen.
4. Vor dem Speichern **Active**, Ziel `main`, leere Bypass-Liste und alle vier Checks samt GitHub-Actions-Herkunft kontrollieren.
5. Speichern und die angelegte Regel nochmals öffnen. Eine nur deaktiviert gespeicherte Regel schützt den Branch nicht.
6. Auf der Repository-Seite beziehungsweise in der Branchansicht prüfen, ob `main` nun als geschützt erscheint. Die aktive Regelliste muss die oben genannten Anforderungen enthalten.

Das Repository ist seit dem vom Nutzer am 29.10.2026 gezeigten Stand öffentlich. GitHub bietet Rulesets für öffentliche Repositories auch mit GitHub Free an. Es ist keine weitere Sichtbarkeitsänderung erforderlich.

## Alternative mit bereits eingerichteter GitHub CLI

Nur in einer lokalen, bereits für dieses Repository administrativ berechtigten GitHub-CLI-Sitzung verwenden. Keine Tokens in Chat oder Repository kopieren. Zuerst vorhandene Regeln lesen:

```powershell
gh api repos/sxba-04/llm-agent-security-lab/rulesets
```

Nur wenn noch keine entsprechende Regel existiert, aus dem Repository-Verzeichnis anlegen:

```powershell
gh api --method POST repos/sxba-04/llm-agent-security-lab/rulesets --input configs/github-main-ruleset.json
```

Anschließend die tatsächlich geltenden Regeln prüfen:

```powershell
gh api repos/sxba-04/llm-agent-security-lab/rules/branches/main
```

Der Erstellungsaufruf erfordert `Administration: write`. Eine erfolgreiche GitHub-Verbindung für Dateien und Pull Requests garantiert diese administrative Berechtigung nicht. Bei fehlenden Rechten keine Regeln umgehen oder Repository-/Kontoschutz abschalten.

## Zusammenarbeit danach

Weiterhin auf Aufgabenbranches arbeiten. Vor dem Merge müssen die vier CI-Jobs erfolgreich und der Branch aktuell sein. Dazu kommen die dokumentierten Codex-Reviews. Bei geändertem Basisstand den Aufgabenbranch regulär aktualisieren, erneut prüfen lassen und dann über den PR mergen. Kein Force-Push auf `main` und keine Abschaltung der Regel für einen bequemen Merge.

## Offizielle Referenzen

Geprüft am 29. Oktober 2026:

- [GitHub: Rulesets erstellen und importieren](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository)
- [GitHub: Branchschutz und erforderliche Checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub REST API: Repository-Regeln](https://docs.github.com/en/rest/repos/rules)
