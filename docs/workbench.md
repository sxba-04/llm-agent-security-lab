# Lokale Laboroberfläche

Die Oberfläche verbindet FastAPI mit React und TypeScript. Diese Auswahl wurde vom Team am 23. Oktober 2026 ausdrücklich getroffen. Sie verwendet denselben Versuchskern und dieselbe Auswertung wie die CLI. Alle über die Oberfläche gestarteten Versuche verwenden ausschließlich das vorgegebene Testmodell. Ein API-Schlüssel wird dafür nicht benötigt oder abgefragt.

## Start unter Windows

Zusätzlich zu Git, uv und Python wird Node.js 24 für den Frontend-Build benötigt. Node.js über einen auf dem Rechner erlaubten Weg installieren; die offiziellen Downloads stehen unter https://nodejs.org/en/download. Danach ein neues Terminal öffnen und `node --version` sowie `npm --version` prüfen.

Im Repository-Verzeichnis:

```powershell
uv sync --locked --extra web --group dev
cd frontend
npm ci
npm run build
cd ..
uv run --locked --extra web security-lab-web
```

Anschließend im Browser `http://127.0.0.1:8765` öffnen. Mit Strg+C im Terminal wird der lokale Dienst beendet. Nach dem einmaligen Paketdownload und Build braucht der Mock-Betrieb keine Modellverbindung, keinen externen Server und keine GPU. Ein laufender Browser ist die Bedienoberfläche; der Python-Prozess muss geöffnet bleiben.

Nach einem Update erst `git pull --ff-only`, dann die Installations- und Buildschritte wiederholen. `npm ci` und `uv sync --locked` verwenden die versionierten Lockdateien. Persönliche Proxy-/Zertifikatseinstellungen verbleiben auf dem jeweiligen Rechner. TLS-Prüfungen werden nicht abgeschaltet.

## Erster vollständiger Durchlauf

1. Unter **Fälle** einen Entwicklungsfall auswählen und Auftrag, Sitzungsrechte und beide Artikelfassungen lesen.
2. Unter **Versuche** einen Fall, B/F/P/FP und die gewünschten Quellfassungen auswählen. Die Oberfläche zeigt die geplante Anzahl; erst der Startknopf erzeugt eine Serie.
3. Nach Abschluss einen Lauf öffnen. Vorschläge, Filter-/Policyentscheidungen, tatsächliche Wirkungen und Ticketzustände getrennt untersuchen.
4. Unter **Vergleich** Zähler, Nenner und offene semantische Urteile ansehen. Mock-Raten sind technische Kontrollen, keine Aussagen zur Angreifbarkeit eines LLM.
5. Ein Review-Paket exportieren. Beide Autoren bewerten unabhängig in getrennten Bewertungsplätzen. Die Verwaltungsansichten mit Schutzvarianten während der Bewertung nicht parallel verwenden.
6. Erst nach vollständiger Eingabe beider Bewertungen einmalig kombinieren; danach sind die Einzelurteile eingefroren. Abweichungen gemeinsam mit mindestens zwei unterschiedlichen Personen und eigener Begründung klären. Einzelurteile bleiben erhalten. Für einen Neubeginn einen neuen Bewertungssatz erstellen.
7. Das vollständige Kampagnenarchiv herunterladen und mit der CLI verifizieren.

Die Trennung der Bewertungsansichten unterstützt Verblindung. Sie ist keine Zugriffssperre gegen einen Autor, der dieselben lokalen Rohdateien selbst öffnet. Manche Ausgaben lassen außerdem eine Schutzmaßnahme vermuten; vollständige Verblindung wird nicht behauptet.

## Daten und Serien

Standardarbeitsverzeichnis ist `runs/`. Neue UI-Serien liegen unter `runs/campaigns/`; gespeicherte CLI-Serien direkt unter `runs/` können ebenfalls geöffnet werden. Über `--workspace` lässt sich ein anderes lokales Arbeitsverzeichnis verwenden. Dieses Verzeichnis wird nicht automatisch über Git synchronisiert.

```powershell
uv run --locked --extra web security-lab-web --workspace runs --port 8765
```

Es läuft höchstens eine UI-Serie gleichzeitig. Browser-Neuladen startet keinen weiteren Versuch. Abbrechen beendet eine Serie an einer kontrollierten Grenze; bereits ausgeführte Wirkungen und gespeicherte Läufe werden erhalten. Abgebrochene Aufgaben erhalten keine gültigen Erfolgsraten. Die Fortschrittsanzeige arbeitet auf der Ebene abgeschlossener Aufgaben; die detaillierte Ereignisansicht zeigt gespeicherte Laufprotokolle, keinen erfundenen Live-Stream.

Nach einem harten Prozessabbruch kann die Werkbank eine nachweislich verwaiste eigene Serie als unterbrochen abschließen. Dafür prüft sie gespeicherte Worker-Zuordnung und Betriebssystem-Dateisperre; ein noch lebender fremder Worker wird nicht übernommen. Originalmanifest und gegebenenfalls alte Zusammenfassung bleiben als Wiederherstellungsbelege unter `provenance/` erhalten. Alte oder über die CLI gestartete Serien ohne eindeutige Worker-Zuordnung werden nicht automatisch umgeschrieben. Beschädigte Kampagnen erscheinen mit Fehlermeldung und bleiben von Auswertung und Bewertung ausgeschlossen; gesunde Kampagnen bleiben erreichbar.

## Lokale Schnittstelle

Die Startfunktion bindet ausschließlich an `127.0.0.1`, verwendet einen Prozess und keinen automatischen Code-Reload. Der Backenddienst prüft Host/Origin und verlangt für Änderungen ein Sitzungstoken. Pfade werden nicht vom Browser frei vorgegeben. Experimentelle Artikel und Modelltexte werden als Text dargestellt, nicht als ausführbares HTML.

Die HTTP-Schnittstelle erlaubt ausschließlich Mock-Serien. Die gesonderte CLI-Modellanbindung bleibt hinter ihren vorhandenen expliziten Freigaben. Eine Einstellung im Browser kann sie nicht aktivieren.

## Entwicklung und Prüfungen

```powershell
uv run --locked --extra web python -m unittest discover -s tests -v
cd frontend
npm test
npm run build
```

Das fertige Frontend wird vom selben FastAPI-Dienst ausgeliefert. So ist für den normalen Betrieb nur ein lokaler Prozess nötig. Sicherheitsentscheidungen und Messgrößen bleiben in Python; React stellt sie dar und sendet ausdrücklich ausgelöste Bedienaktionen.

Der optionale Browser-Integrationstest startet den gebauten Dienst selbst und verwendet ausschließlich synthetische Testdaten unter `runs/browser-ci/`:

```powershell
cd frontend
npx playwright install chromium
npm run test:e2e
```

Dafür darf kein anderer Laborprozess auf Port 8765 laufen. Playwright verwendet einen eigenen Dienst und bricht bei belegtem Port ab, damit keine Testdaten in einem persönlichen Arbeitsverzeichnis entstehen. Der Browserdownload ist nur für Entwicklungstests erforderlich, nicht für die normale Bedienung mit eurem vorhandenen Browser.
