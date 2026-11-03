# Qualitätskorrekturen vom 3. November 2026

## Ausgangspunkt und Umfang

Ausgangspunkt ist `d966880aa01e4a340bce3d84c381fcde13948de9`.
Das anhand des GitHub-CI-Artefakts geprüfte Sonar-Inventar enthält **59**, nicht
60 ungelöste Meldungen: 41 Code Smells, 17 vom Scanner als Vulnerability
klassifizierte Meldungen und einen Bug. Eine Scanner-Klassifizierung ist noch
kein Nachweis einer ausnutzbaren Schwachstelle. Die Analyse
`ee65b7bc-c8ef-4ee4-bcc7-aa37ec70fac3` vom `2026-11-03T10:45:23Z` nennt genau
diese Ausgangsrevision. Herkunft: Workflow `41621140919`, Artefakt
`13223857701`, ZIP-SHA-256
`4ad0cf9c5f0f00a64594f387242199ad2367d2fd736f135318fda92799b5377c`.

Der Auftrag umfasst konkrete Sonar-Korrekturen und eine ausführliche
[Ausbauplanung](roadmap-2026-11.md). Dark Mode, native Apps, eine Datenbank und
weitere kostenpflichtige Dienste werden in dieser Änderung nicht eingeführt.

## Änderungen

| Bereich | Konkrete Verbesserung |
|---|---|
| 22 Komplexitätsmeldungen S3776 | API-Verkabelung, Requestzustand, Datei-/Archivprüfung, Fallvalidierung, Bewertung, Vergleich, Providerantworten und Versuchsausführung nach Verantwortung zerlegt |
| API-Antwortdokumentation S8415 (11 Bestandsmeldungen) | Handler aus der großen App-Closure in eine pro App erzeugte Klasse überführt; alle vier OpenAPI-Schemata bleiben identisch. Die bereits vorhandene globale Fehlerdokumentation wird nicht als neue Laufzeitvalidierung dargestellt |
| CI-Summaries S7689 (2) | Eingebettetes Python aus YAML-Shellblöcken in einen separat getesteten Python-Helfer verschoben; Ausgabe bleibt gleich |
| React S6479 (2) | Stabile inhaltsbasierte Schlüssel mit Duplikatzähler; wiederholte Evidenz und Leerzeilen bleiben vollständig erhalten |
| Formular S6853 (1) | Eindeutige Label-/Checkbox-Verknüpfung mit React useId; flache Beschriftung mit Fallkennung als Name und Ziel/Szenario als Beschreibung |
| Originprüfung S6353 (1) | Kürzere Ziffernklasse mit explizitem ASCII-Modus; Unicode-Ziffern bleiben abgelehnt |
| Cachebereinigung S7504 (1) | Veraltete Schlüssel zuerst sammeln, anschließend entfernen; keine Mutation der iterierten Ansicht |

Eine bearbeitete Stelle ist nicht automatisch eine vom Scanner geschlossene
Meldung. Insbesondere globale API-Antwortmetadaten und verschachtelte
Labeltexte können statisch weiter gemeldet werden. Maßgeblich sind die neue
Analyse und ihr Bezug zum tatsächlichen Commit. Es wurden keine Regeln,
Quality Gates oder Analysebereiche abgeschaltet und keine Sonar-Meldungen
remote als erledigt markiert.

## Bewusst erhaltenes Verhalten

Die vorhandenen Einzelbewertungen bleiben historische Nachweise unter
[Sonar-Triage](sonar-triage/README.md). Erneut geprüft wurden:

- **14 S8707-Dateipfadmeldungen:** die konkret gemeldeten Datenflüsse beginnen
  an ausdrücklich gewählten lokalen Operatorpfaden. HTTP-Kennungen und
  Archivmitglieder bleiben separat streng eingegrenzt. Diese Aussage gilt
  nicht pauschal für jede Dateioperation oder beliebige künftig neue Aufrufer.
- **S4830:** der HTTPS-Transport verwendet weiterhin einen sicheren
  Standardkontext mit Zertifikats- und Hostnamenprüfung sowie gesperrten
  Redirects. Ein Zertifikatsfehler wird ohne Wiederholung bereinigt behandelt.
- **S8392:** der gesonderte authentifizierte Render-Dienst muss an seiner
  Container-Schnittstelle lauschen; der lokale Launcher bleibt Loopback-only.
- **S2245:** der reproduzierbare Zufallsgenerator steuert die wissenschaftliche
  Versuchsreihenfolge, keine Geheimnisse oder Sitzungen.
- **S2201:** strenges Dekodieren dient hier der UTF-8-Validierung durch eine
  Ausnahme; das Verwerfen des Rückgabewerts ist beabsichtigt.
- **S1874:** der zusätzliche beforeunload-Rückgabewert schützt ungespeicherte
  Bewertungen in älteren Browsern. Eine Änderung benötigt eine klare
  Browser-Supportentscheidung und ersetzt ohnehin keine Konflikterkennung.

Zur eindeutigen Zuordnung der Review-Pfade: `AaGMS_8-7rRJBvbBA1oD`
bezieht sich im Ausgangsstand auf das Lesen des Mappings (review.py:52),
`AaGMS_8-7rRJBvbBA1oE` auf das Lesen der Pakete (:75),
`AaGMS_8-7rRJBvbBA1oB` auf das Erzeugen des neuen Review-Verzeichnisses (:147)
und `AaGMS_8-7rRJBvbBA1oC` auf das Lesen der Ratingdatei (:215).

## Ausgeführte lokale Nachweise

Geprüfter integrierter Codestand: `53f482406e76dfa11b42a05d3e99c253a8a8c344`,
Linux mit Python 3.12.14 und den unveränderten Lockdateien.

- `uv sync --locked --extra web --group dev` erfolgreich.
- Vollständige Python-Suite: **337 Tests ausgeführt, 336 bestanden, ein
  Windows-spezifischer Test auf Linux übersprungen**.
- Frontend: `npm ci`, **79/79 Tests** und TypeScript-/Vite-Build erfolgreich.
- 96 vollständige Mock-Protokolle, Einzelbewertungen und Summary stimmen
  mit dem Ausgangsstand überein. Ausschließlich die Laufzeit wurde auf null
  normalisiert; feste Seeds und Run-IDs waren für beide Stände gleich.
- Eine unabhängige Prüfung des Versuchskerns verglich zusätzlich **13.824**
  deterministische Grenzfälle einschließlich vollständiger Protokolle,
  übergebener Modellnachrichten sowie Abbruch-/Zeitprüfungsaufrufen ohne Abweichung.
- Die vier OpenAPI-Schemata (lokal/gehostet und UI/API) sind vor/nach dem
  API-Refactoring nach kanonischer Serialisierung identisch.
- Neue Tests prüfen requestlokale Antwort-/Bodylimits, ASCII-Originports,
  Antwortbelege vor Abbruch/Zeitlimit, ungültiges kombiniertes Review-JSON,
  CI-Ausgaben und stabile Frontend-Evidenzidentität.
- Storage-Gegenprüfung: 7.371 ungültige Fallvarianten stimmen in Annahme,
  Ausnahmetyp und Fehlermeldung mit dem Ausgangsstand überein.

Die lokale Installation des Playwright-Chromium-Browsers scheiterte an
ungültigen Download-ZIP-Dateien. Dieser lokale Browserlauf wird daher nicht
als bestanden gezählt. Die vorhandene Windows-/Linux-Browser-CI muss am
jeweils aktuellen PR-Stand erfolgreich abgeschlossen werden. Testergebnisse
und Coverage-Prozente der CI sind am zugehörigen PR einzusehen; eine erfolgreiche
PR-Analyse allein beweist noch keine neue Anzahl offener Main-Befunde.

## Review und wissenschaftliche Auswirkungen

API, Versuchskern und Speicherschicht wurden jeweils von einer anderen
KI-gestützten Prüfinstanz als dem Implementierungsagenten untersucht. Die integrierte Codeänderung wurde bei `53f4824` zusätzlich unabhängig
geprüft; 70 modulübergreifende Tests bestanden ohne übersprungene Tests.
Aktuelle CI sowie Codex-Code- und Security-Reviews werden vor einem Merge
geprüft. Die vom Eigentümer erlaubte
Copilot-Quotenausnahme gilt weiterhin; sie wird nicht als bestandener Review gewertet.

B/F/P/FP, Gateway-Reihenfolge, Beobachtungen, Fehlergrenzen, Paarbildung,
Kennzahlennenner, Originalbewertungen, Archivprovenienz und Kostenreservierung
bleiben erhalten. Es wurden keine Modellaufrufe durchgeführt, menschlichen
Bewertungen erfunden oder vorhandenen Studienbelege umgeschrieben.
Der Umbau verbessert Wartbarkeit; er ist kein empirisches Ergebnis zur
Wirksamkeit einer Schutzvariante.

## Nachprüfung der ersten PR-Analyse

Die erste Sonar-PR-Analyse von `d8e72556886e5b9828e2d485bbabef923288368f`
bestand das Gate mit 91,9 % New-Code-Coverage und ohne neue Security Hotspots,
zeigte aber zwei Hinweise. Vor dem Merge wurden beide nachbearbeitet:

- Der neue Authentifizierungshelfer liefert jetzt einheitlich ein typisiertes
  Dreiertupel oder `None`. Ein explizites `None` entspricht exakt dem bisherigen
  Standardargument von `reject`; HTTP-Status, JSON und Reihenfolge bleiben gleich.
- Die Fallkarte verwendet eine flachere native Beschriftung. Die Fallkennung
  benennt die Checkbox, Ziel und Szenario bilden ihre Beschreibung. Die ganze
  Karte bleibt anklickbar; das lokale Layout wurde darauf abgestimmt.

Die vorherigen grünen Reviews und Checks gelten nicht automatisch für diesen
Nachtrag. Der zugehörige PR dokumentiert die erneute Prüfung des aktuellen
Heads und später das tatsächlich exportierte Main-Inventar.
