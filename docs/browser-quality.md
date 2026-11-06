# Browser-, Mobil- und Barrierefreiheitsprüfung

Die Prüfungen verwenden synthetische Fälle und Mock-Läufe. Sie ersetzen keine
menschliche Studienbewertung und führen keine kostenpflichtigen Modellaufrufe aus.
Jeder lokale Playwright-Start erzeugt einen eigenen temporären Workspace unter
`runs/browser-ci/`. Die HTTPS-Tests verwenden getrennte temporäre Verzeichnisse
unter `runs/browser-hosted/`; Zugangscode und GitHub-Identität sind Test-Fixtures.

## Abdeckung

| Prüfung | Chromium | Firefox / WebKit |
|---|---|---|
| Bestehender vollständiger lokaler Ablauf | Windows und Linux | – |
| Tastatur-Tabs, getrennte Bewertungsentwürfe, Archivdownload | Windows und Linux | Linux-Smoke |
| PDF → Mock-Versuch → Vergleich → Entwurf → Archiv bei 320, 390, 768, 1440 px | Windows und Linux | – |
| WCAG 2 A/AA und 2.1 AA mit axe: Übersicht, Fall, Vorbereitung, PDF in Hell/Dunkel; Vergleich/Bewertung mobil | Windows und Linux | – |
| Theme-Präferenz, Systemwechsel, geschlossene Navigation und Fokus | Windows und Linux | – |
| HTTPS-Anmeldung mit Zugangscode; PDF-/Archivdownload | Linux | Linux-Smoke |
| Synthetischer GitHub-Callback und eigene Sitzungsverwaltung über HTTPS | Linux | – |
| Zwei visuelle Referenzen: Quellenvergleich Hell/Dunkel | Linux | – |

Die Einschränkung der zusätzlichen Engines auf wenige kritische Abläufe hält die
Laufzeit begrenzt. Die Seiten werden mit dem echten FastAPI-Dienst geprüft.
Es gibt keine pauschal ausgeblendeten axe-Regeln. Automatische Barrierefreiheitstests
weisen nicht alle WCAG-Anforderungen nach; Screenreader, echte Bildschirmtastatur,
Touch-Bedienung und Vergrößerung auf realen Geräten bleiben manuell zu prüfen.
Die vorübergehende Höhe von 420 px prüft nur den eingeschränkten Platz für Eingaben.

## Lokal ausführen

Im Repository zuerst `uv sync --locked --extra web --group dev`, danach im
Verzeichnis `frontend`:

```text
npm ci
npm run browsers:install
npm run build
npm run test:e2e
```

Für eine reine Chromium-Prüfung, etwa unter Windows:

```text
npm run browsers:install:chromium
npm run test:e2e:chromium
```

Die vorhandene Anleitung für HTTPS-Fixtures in [Hosting](hosting.md) beschreibt
den separaten Build nach `dist-hosted`; danach prüft `npm run test:e2e:hosted`
alle konfigurierten Engines. Linux-CI installiert benötigte Browserbibliotheken mit
Playwrights `install --with-deps`. In einer eingeschränkten Umgebung kann man
mit `LAB_CHROMIUM_EXECUTABLE` ausdrücklich einen vorhandenen Chromium-Pfad wählen.
Dieser Schalter betrifft ausschließlich die Testkonfiguration. Eine abweichende
Browserversion muss im Prüfnachweis genannt werden; die CI verwendet die gelockte
Playwright-Version und ihre Browser. Fehlende Pakete, Startverbote oder übersprungene
Prüfungen gelten nicht als Erfolg.

## Visuelle Referenzen bewusst pflegen

`npm run test:visual` prüft zwei stabile Ausschnitte derselben synthetischen
Fallansicht. Sie enthalten keine Zeitstempel oder veränderlichen Kampagnenzahlen.
Die Referenzen gelten nur für Linux/Chromium, weil Schrift-Rasterung zwischen
Betriebssystemen abweicht. Windows prüft dieselben Funktionen ohne Pixelvergleich.

Ein fehlendes oder abweichendes Referenzbild lässt die Prüfung fehlschlagen.
Zum beabsichtigten Aktualisieren auf einem passenden Linux-System:

```text
npm run test:visual:update
```

Anschließend beide Bilder visuell vergleichen, den Anlass dokumentieren und die
PNG-Dateien unter `frontend/e2e/visual.spec.ts-snapshots/` mit dem geprüften Code
versionieren. CI aktualisiert niemals automatisch Referenzen. Bei der ersten
Erstellung auf GitHub kann ein fehlgeschlagener Lauf die Bilder als
`browser-evidence-Linux` liefern; sie werden vor der Übernahme geprüft.

## Nachweise und Grenzen

Playwright speichert HTML-Bericht, Fehler-Screenshots/Traces sowie die axe-Ergebnisse
als JSON-Anhänge. Die CI hält diese synthetischen Artefakte 14 Tage bereit. Nach
Änderungen zählen nur Tests auf dem aktuellen Commit. Ein Screenshot allein ist
kein bestandener Ablauf und eine grüne CI ist keine menschliche Abnahme.

Die Test- und CI-Erweiterung wurde mit Codex erstellt. Ausgeführte Prüfungen und
verbleibende Grenzen werden im jeweiligen PR und im aktuellen Prüfstand angegeben.
