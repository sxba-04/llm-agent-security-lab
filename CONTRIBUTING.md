# Gemeinsam am Labor arbeiten

Die verbindlichen Projektregeln stehen in [AGENTS.md](AGENTS.md), die
Sicherheitsgrenzen in [SECURITY.md](SECURITY.md). Für lokale Einrichtung und
gemeinsame VS-Code-Tasks siehe [README](README.md).

1. Aktuellen `main` holen und einen eigenen Branch verwenden. Änderungen an
   Versuchsdesign, Fällen oder Bewertung vor einer Messserie gemeinsam abstimmen.
2. Abhängigkeiten ausschließlich über `uv.lock` und `frontend/package-lock.json`
   synchronisieren. Keine Zugangscodes, Modellschlüssel oder echten Tickets
   einchecken. Beispiele und Fehlerbelege müssen synthetisch sein.
3. Betroffene Tests ausführen und einen PR mit Anlass, Verhalten, tatsächlichen
   Prüfungen und KI-Beiträgen öffnen. Eine erzeugte Datei oder grüne Coverage-Zahl
   ersetzt keine fachliche Abnahme durch Sebastian und Jonah.
4. Aktuelle CI und Reviews prüfen; Befunde nachvollziehbar bearbeiten. Updates von
   Dependabot durchlaufen denselben Prozess. Kein pauschales Auto-Merge.
5. Nach dem Merge erfolgt die Veröffentlichung aus `main`. Wichtige Archive vor
   einem Deployment aus der kostenlosen Testumgebung herunterladen.

## Prüfungen und Coverage

```sh
uv sync --locked --extra web --group dev
uv run --locked --extra web coverage run -m unittest discover -s tests -v
uv run --locked --extra web coverage xml
uv run --locked --extra web coverage html
npm ci --prefix frontend
npm run test:coverage --prefix frontend
npm run build --prefix frontend
```

Coverage-Dateien bleiben lokal beziehungsweise in den CI-Artefakten und werden
nicht eingecheckt. Browser-Integrationstests und synthetische Serien sind
zusätzliche Prüfungen; ihre Ausführung wird nicht in diese Unit-Coverage
eingerechnet. [Qualitätswerkzeuge](docs/quality-tooling.md) erläutert die Berichte,
Sonar-Konfiguration und Grenzen.

Fehler und Wünsche lassen sich über die Issue-Formulare erfassen. Mögliche
Sicherheitslücken bitte über
[private Sicherheitsmeldungen](https://github.com/sxba-04/llm-agent-security-lab/security/advisories/new)
melden; keine Zugangsdaten oder ausnutzbaren Details in öffentliche Issues setzen.
