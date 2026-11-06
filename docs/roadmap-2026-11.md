# Ausbauplan für die Forschungswerkbank

**Umsetzung:** Der [Änderungsnachweis vom 6. November 2026](roadmap-implementation-2026-11-06.md)
beschreibt die implementierten Pakete und die noch offenen fachlichen und
betrieblichen Abnahmen. Der folgende Text bewahrt den ursprünglichen Planungsstand.

Stand: 3. November 2026. Diese Analyse bezieht sich auf den Ausgangsstand
`d966880aa01e4a340bce3d84c381fcde13948de9`. Sie unterscheidet vorhandene Funktionen,
konkrete Verbesserungen und spätere Optionen. Die folgenden Pakete sind Vorschläge,
keine bereits implementierten Funktionen oder Freigaben für neue Kosten und Modellaufrufe.

Die Werkbank sollte als verlässliches Untersuchungsinstrument weiterentwickelt werden.
Empfohlen sind zuerst überschaubare Qualitätskorrekturen, dann Dark Mode,
mobile Bedienbarkeit und gezielte Tests. Eine native App, eine neue Datenbank oder
ein Wechsel des Hosters sind derzeit nicht erforderlich. Die fachliche Abnahme,
äußere Isolation und ein begrenzter Modellpilot bleiben Voraussetzungen der Hauptmessung.

## Ausgangslage

| Bereich | Vorhanden | Tatsächliche nächste Lücke |
|---|---|---|
| Oberfläche | React/TypeScript, mobile Navigation, mehrere CSS-Breakpoints, Zustands- und Fehlermeldungen | Viele feste Farben und sehr kleine mobile Hilfstexte; kein umschaltbares Theme, kein umfassender visueller Prüfstand |
| Anmeldung | GitHub-Freigabeliste, PKCE/State, begrenzte eigene Sitzungen, Zugangscode | Jonahs eigene Live-Anmeldung; keine erzwungene Unabhängigkeit wissenschaftlicher A/B-Bewertungen |
| Tests | 328 Python-Testfunktionen, 76 Frontend-Tests im geprüften Ausgangsstand, Chromium-End-to-End-Tests unter Windows/Linux und vier gehostete HTTPS-Szenarien | Weitere Browser, vollständige mobile Arbeitsabläufe, automatisierte Barrierefreiheitsprüfung und Produktions-Ressourcenmessung |
| Mobile Tests | Ein Browserablauf prüft Navigation und Überlauf bei 390 × 844 Pixeln | PDF-Import, Vergleich, Bewertung, Dialoge und Sitzungen bei mehreren Breiten und mit Bildschirmtastatur |
| Datenerhalt | 1-GB-Disk, geprüfte Archive, Integritätskontrollen, atomare Schreibvorgänge und Unterbrechungsbehandlung | Regelmäßige externe Sicherung und dokumentierte Wiederherstellungsübung |
| Qualität | Sonar, CodeQL, Dependency Review, Dependabot, Reviews und Coverage in CI | 59 offene Sonar-Meldungen im Ausgangsinventar; hohe Komplexität einzelner Funktionen |
| Dokumentation | Versionierte Anleitungen, Abnahmevorlage, Architektur, Bedrohungsmodell, Windows-/VS-Code-Setup und veröffentlichtes Wiki | Regelmäßige Aktualitätskontrolle, leichter Einstieg nach Rolle und dokumentierte Releases |
| Betrieb | Pages und ein Render-Prozess mit 0,5 CPU/512 MB, Healthcheck, automatische Bereitstellung nach erfolgreichen Prüfungen | Ressourcenmessungen, Speicherwarnungen, Betriebsdiagnose und geübter Rollback |

Die Zahlen sind Ausgangsnachweise, keine feste Zielgröße für Tests. Ein grünes
Quality Gate bedeutet nicht null Bestandsbefunde. Die Sonar-Korrekturen und ihre
erneute Analyse werden im zugehörigen Änderungsnachweis getrennt dokumentiert.

## Empfohlene Reihenfolge

Aufwände sind grobe Planungswerte in Personentagen von etwa sechs konzentrierten
Arbeitsstunden, einschließlich Tests und Review. Sie sind keine Zusagen und werden
nach einem kleinen Prototyp überprüft. Pakete können sich überlappen; die Summe
ist kein Kalenderplan für die Studienarbeit.

| Reihenfolge | Paket | Nutzen und Abschlusskriterium | Grober Aufwand |
|---|---|---|---|
| 1 | Sonar und begrenztes Refactoring | Komplexe Funktionen nach Verantwortung aufteilen; fachliche Ergebnisse, Fehlergrenzen und Evidenz unverändert; aktuelle CI und Reviews bestanden | 3–6 Tage |
| 2 | Theme und mobile Bedienbarkeit | Hell/Dunkel/System, konsistente Statusfarben; Kernabläufe bei 320–1440 px und Tastaturbedienung geprüft | 2–4 Tage |
| 3 | Browser und Barrierefreiheit | Begrenzte Smoke-Tests in Chromium, Firefox und WebKit auf geeigneten Runnern; kritische Abläufe, Kontraste und Fokusführung geprüft | 2–3 Tage |
| 4 | Sicherung und Wiederherstellung | Export außerhalb des Dienstes, Prüfsummenprüfung und Wiederherstellung in einen getrennten Workspace nachgewiesen | 1–3 Tage |
| 5 | Lokaler Diagnose- und Einrichtungsablauf | Frischer Windows-Klon bis Mock-Lauf/Archiv ohne verdeckte manuelle Korrekturen; klare Proxy-/Zertifikatsdiagnose | 1–2 Tage |
| 6 | Fachliche Abnahme und Pilotvorbereitung | Repräsentative Fälle, PDF-Texte, Rubrik und äußere Isolation geprüft; Pilotumfang und Kosten vorab festgelegt | Technisch 2–4 Tage plus Autorenprüfung |
| 7 | Kampagnen- und Bewertungskomfort | Verständliche Kampagnennamen, Vergleichsexport und erkennbare Bearbeitungskonflikte; vorhandene Filter und Fortschrittsanzeigen weiterverwenden | 2–4 Tage |
| 8 | Leistung und optionale SQLite-Metadaten | Erst reale Engpässe messen; einen Index nur bei belegtem Nutzen einführen und aus Belegen wieder aufbauen können | Messung 1–2 Tage; Migration separat |

Die Pakete 2 und 3 sollten gemeinsam abgenommen werden. Die Hauptmessung darf
nicht auf zusätzliche Komfortfunktionen warten, sobald das Untersuchungsinstrument
fachlich und technisch bereit ist. Der Versuchsplan priorisiert Vergleichbarkeit,
saubere Kontrollfälle und Reproduktion vor einem großen Funktionsumfang.
Unabhängig von dieser Produktreihenfolge müssen Sicherung und Wiederherstellung
vor echten Pilotaufrufen und der Sammlung benötigter Studienbelege nachgewiesen sein.

## Dark Mode und mobile Oberfläche

Ein Theme beginnt mit semantischen CSS-Variablen für Hintergrund, Oberfläche,
Text, dezente Schrift, Trennlinien, Fokus und Statusfarben. Bestehende feste
Farben werden systematisch darauf umgestellt. Die Auswahl umfasst **Hell,
Dunkel und System**; `prefers-color-scheme` und `color-scheme` unterstützen die
Systempräferenz und native Formularelemente. Nur die unkritische Theme-Präferenz
darf lokal gespeichert werden, keine Zugangscodes, Labortoken oder Versuchsdaten.

Zur Abnahme gehören Anmeldung, Sitzungsmenü, Tabellen, Code-/Ereignisansichten,
PDF-Textvorschau, Fehlerzustände und deaktivierte Bedienelemente in beiden Themes.
Status darf nicht ausschließlich an Rot/Grün erkennbar sein. Ein heller Blitz
beim Start soll vermieden werden; Druckansichten behalten eine gut lesbare Darstellung.

Mobile Nutzung wird im bestehenden React-Webfrontend ausgebaut. Besonders zu
prüfen sind Bewertungseingaben, lange Belegtexte, Vergleichstabellen, Uploads,
Downloadfehler und die Bedienung mit eingeblendeter Bildschirmtastatur. Tabellen
dürfen bei Bedarf innerhalb ihres eigenen Bereichs horizontal scrollen; die
gesamte Seite soll es nicht. Hilfstexte sollten nicht immer weiter verkleinert
werden, um Platzprobleme zu verstecken. Fokusführung, Escape-Verhalten,
ausreichende Klickflächen und vergrößerte Schrift gehören zu diesem Paket.
Konkret muss die geschlossene mobile Navigation aus der Tab-Reihenfolge
verschwinden; Tabs benötigen passende Panel-Bezüge und Pfeiltastensteuerung.
Dies sind Befunde der Codeprüfung, noch keine manuelle Screenreader-Abnahme.

React Native verwendet native Android-/iOS-Komponenten und wäre ein zusätzlicher
Anwendungsclient mit eigener Navigation, Datei-/Downloadbehandlung, OAuth-Rückkehr
und Test-/Veröffentlichungskette. Der vorhandene DOM-/CSS-Aufbau lässt sich nicht
einfach als native Oberfläche übernehmen. Ohne konkrete Anforderungen an native
Gerätefunktionen steht dieser Aufwand derzeit in keinem guten Verhältnis zum Nutzen.
Eine installierbare Web-App wäre später die kleinere Option. Ein Service Worker
darf dabei keine geschützten API-Antworten oder Tokens unbemerkt dauerhaft speichern;
Offline-Bewertungen benötigen zuvor ein eigenes Konflikt- und Synchronisationskonzept.

## Gezielte Ergänzungen der Tests

Bestehende Fehlergrenzen werden erhalten: Tests decken bereits unter anderem
vollen Speicher, konkurrierende Dateischreiber, Prozessabbrüche, beschädigte
Archive, unbestätigte PDF-Quellen, fremde Sitzungen und synthetische abgelehnte
GitHub-Konten ab. Diese Prüfungen müssen nicht als neue Features erneut erfunden werden.

| Ergänzung | Konkrete Abnahme |
|---|---|
| Browsermatrix | Wenige kritische Smoke-Tests für Anmeldung, Download und Bewertungsentwurf in Chromium/Firefox/WebKit; keine vollständige Kombination aller Betriebssysteme und Bildschirmgrößen; Unterschiede dokumentieren |
| Mobile Abläufe | Login → Fall → Mock-Kampagne → Protokoll → Bewertung → Archiv bei mehreren Breiten; kein verdeckter Fokus oder unbedienbares Formular |
| Barrierefreiheit | Automatisierte Prüfung etwa mit axe plus manuelle Tastatur-/Screenreader-Stichprobe; Kontrast, Namen, Fehlermeldungen und Fokus prüfen |
| Visuelle Regression | Wenige stabile Referenzbilder für beide Themes und zentrale Ansichten, feste Testdaten/Schriften und eine bewusst geprüfte Aktualisierung |
| Schema- und Migrationstests | Alte Manifest-/Archivbeispiele bleiben lesbar oder werden mit verständlicher Versionsmeldung abgelehnt; keine stillschweigende Umetikettierung |
| Ressourcen und Last | Synthetische große PDFs, lange Protokolle und wachsende Kampagnenlisten auf 512 MB messen; Laufzeit, Spitzen-RAM, Dateizahl, Antwortzeiten und Ablehnung konkurrierender Starts protokollieren |
| Wiederherstellung | Verifiziertes externes Archiv in einen leeren separaten Workspace importieren und Belege, Bewertungen und Quellen erneut prüfen |
| Zusammenarbeit | Gleichzeitige Bewertungsänderungen erkennen; keine unbeabsichtigte Überschreibung, Originalurteile und Klärungsversionen erhalten |
| API-Kompatibilität | Alte und neue Oberfläche gegen die jeweils zulässige API-Version prüfen, weil Pages und Render getrennt bereitgestellt werden |

Zusätzliche Coverage wird an ungetesteten Entscheidungen und Fehlerpfaden
ausgerichtet. Ein pauschales Ziel von 100 Prozent wäre kein Ersatz für realistische
Tests. Property-/Fuzz-Tests können später begrenzte Parser- und Pfadfälle ergänzen;
sie dürfen keine unbegrenzte Last, Netzaufrufe oder echten Modellkosten auslösen.

## Refactoring und Softwarequalität

Die erste Refactoring-Runde trennt Konfigurationsprüfung, Datenvalidierung,
Protokollauswertung, API-Verkabelung und Dateizugriff in benannte Funktionen.
Fehler werden weiterhin an derselben Vertrauensgrenze abgelehnt. Gerade beim
Versuchskern sind identische Reihenfolge, Zähler, Ereignisse und beobachtete
Wirkungen wichtiger als ein kleinerer Scannerwert. Die Bedingungen B/F/P/FP
bleiben derselbe Ausführungspfad mit unveränderten Eingriffspunkten.

Danach sind kleinere API-Router und eine schmale Speicherschnittstelle sinnvoll,
wenn damit konkrete Änderungen leichter werden. Keine zusätzliche Architektur
aus Services, generischen Repositories und Abstraktionen ohne realen Bedarf.
Frontend-Komponenten sollten Darstellung, Formularzustand und API-Aufrufe
nachvollziehbar trennen; fachliche Urteile bleiben im gemeinsamen Python-Kern.

Als nächste Werkzeugergänzung ist ein kleiner, gemeinsam vereinbarter
Lint-/Formatierumfang sinnvoll, etwa Ruff für Python und eine abgestimmte
Frontend-Formatierung. Typprüfung zunächst an Modulgrenzen einführen. Eine
Massenformatierung gehört in einen eigenen PR und nicht zwischen fachliche
Änderungen. Keine Sonar-Regel abschalten oder Meldungen pauschal ausblenden, um
eine schöne Zahl zu erreichen. Begründete Fehlalarme benötigen einen konkreten
Datenfluss, Voraussetzungen, Gegenbeispiele und zugehörige Tests.

## Speicherung und Datenbankentscheidung

Die Anwendung besitzt bereits eine Speicherschicht: JSON/JSONL für Kampagnen,
Ereignisse und Bewertungen sowie PDFs und prüfbare ZIP-Archive. Eine Datenbank
ist deshalb keine Voraussetzung für dauerhafte Daten. Die aktuelle Disk ist
für den bestehenden einzelnen Prozess eingerichtet und über Neustarts geprüft.

| Option | Passender Einsatz | Konsequenz |
|---|---|---|
| Bestehende Dateien | Zwei Betreiber, eine aktive Kampagne, prüfbare Rohdaten und portable Archive | Beibehalten; Listen und Dateizugriffe messen, Schemas versionieren |
| SQLite | Schnelle Suche, Metadatenindex, Transaktionen und spätere Verwaltung bei einem Backend | Erste Datenbankoption; auf echter persistenter Disk, keine direkte Freigabe an mehrere Rechner |
| PostgreSQL | Mehrere Backend-Instanzen oder deutlich mehr gleichzeitig schreibende Nutzer | Eigener Betrieb/Kosten, Migration und Verbindungspooling; heute nicht erforderlich |

Ein sinnvoller erster SQLite-Schritt wäre ein **wiederaufbaubarer Index** für
bestehende Status- und Zeitstempeldaten. Neue Namen und Tags benötigen zuerst
versionierte kanonische Metadaten, die auch exportiert und wiederhergestellt
werden; nur dann ist der daraus erzeugte Index vollständig wiederaufbaubar.
Wissenschaftliche Originalbelege bleiben zunächst die kanonische Quelle. Vor einer weitergehenden Migration sind
Schema-Versionen, Transaktionen, Konfliktverhalten, Export/Import, Abbruch und
Rollback zu testen. Zwei konkurrierende Wahrheiten zwischen Dateien und Datenbank
sind zu vermeiden. SQLite lässt jeweils nur einen aktiven Schreiber zu; die
konkrete Nutzung entscheidet über seine Eignung, nicht die bloße Zahl der Konten.
Eine aktive SQLite-Datenbank würde über eine geeignete Online-Backupfunktion
gesichert; eine ungeprüfte Dateikopie während Schreibvorgängen genügt nicht.

Eine Datenbank würde weder die unabhängige Urteilsbildung noch die äußere
Isolation herstellen. Persistente Laborsitzungen wären ebenfalls eine eigene
Sicherheitsentscheidung; Tokens gehören weiterhin nicht in Browser-LocalStorage.

## Deployment und Betrieb

GitHub Pages plus Render passt zum derzeitigen Umfang. Der Betrieb bleibt bei
einer Instanz und einem Prozess. Eine Render-Disk ermöglicht keine horizontale
Skalierung und keine unterbrechungsfreie Bereitstellung nach dem üblichen
Zero-Downtime-Verfahren. Laufende Kampagnen müssen vor einer geplanten
Bereitstellung sichtbar sein; ein unterbrochener Lauf darf nicht automatisch
erneut Modellaufrufe ausführen. Ein Anbieterwechsel löst diese Anwendungsfragen nicht.
Pages und Render werden nicht atomar aktualisiert. Änderungen am API-Vertrag
müssen deshalb einen Übergang mit alter Oberfläche oder altem Backend vertragen
oder eine klar erklärte Versionsgrenze mit sicherer Fehlermeldung haben.

Als nächster Betriebsschritt werden Sicherung und Wiederherstellung festgelegt:
Was wird exportiert, wohin, wie lange aufbewahrt, wer kontrolliert Fehler und
wie wird eine Wiederherstellung geprüft? Bestehende Render-Snapshots und die
anwendungseigenen Archive haben unterschiedliche Aufgaben. Ein neues externes
Backupziel benötigt eine konkrete Auswahl; zusätzliche Abos sind durch diesen
Plan nicht beauftragt. Das bestehende Speicherlimit bleibt 1 USD/Monat.
Der Sicherungsumfang umfasst auch noch keiner Kampagne zugeordnete PDF-Originale,
Originalbewertungen, deren Versionshistorie sowie den eingefrorenen Code mit
Lockdateien. Integrität und Vollständigkeit werden getrennt geprüft: Ein
unvollständiger Versuch kann unveränderte, gültige Teilbelege besitzen.
Eine Kampagnen-ZIP allein ist
kein vollständiges Backup des gesamten Forschungsbestands. Die Disk kann nicht
einfach in einen separaten Render-Cronjob eingebunden werden; der automatische
Export benötigt einen tatsächlich unterstützten Zugriffsweg und einen
nachvollziehbar konsistenten Datenstand.

Weitere sinnvolle Maßnahmen sind Warnungen vor voller Disk, begrenzte strukturierte
Logs mit Korrelationskennung und eine nachvollziehbare Release-/Rollback-Anleitung.
Keine Tokens, OAuth-Codes oder vollständigen vertraulichen Beleginhalte in Logs.
Ein Healthcheck soll keine Modellanfrage starten. CPU/RAM und Antwortzeiten werden
gemessen, bevor Compute vergrößert oder eine neue Datenbank gebucht wird.

## Lokale Umgebung und Dokumentation

Lockdateien, Python-Version, Node-Vorgabe und VS-Code-Aufgaben sind bereits
vorhanden. Die nächste Verbesserung ist ein ausschließlich lesender Diagnosebefehl,
der Versionen, vorhandenen Frontend-Build, Portbelegung, freien Speicher und
Pfadberechtigungen prüft und konkrete Fehler erklärt. Installation und Build
bleiben getrennte, explizite Schritte. Die vorhandenen Windows-Anleitungen zu
Proxy und Unternehmenszertifikaten werden durch diese Diagnose ergänzt;
TLS-Prüfungen werden dabei nicht deaktiviert. Eine leere Entwicklungsumgebung
auf Jonahs Rechner ist eine wertvolle reale Abnahme neben dem CI-Runner.

VS Code und JetBrains sollten dieselben CLI-Befehle aufrufen. Ein Dev Container
ist optional und nicht Voraussetzung für die beiden vorhandenen Windows-Setups.
Lokale und gehostete Daten bleiben getrennt; ein Kopieren von Live-Secrets in
Projektdateien ist kein Einrichtungsschritt.
Die bestehende VS-Code-Aufgabe „Alle Tests“ führt Python-Tests aus; eine
eindeutige Benennung und ein zusätzlicher Gesamtcheck für Backend, Frontend und
Browser vermeiden Missverständnisse. Unterstützte Python-/Browser-Versionen
werden festgelegt und passend getestet, statt aus einer offenen Versionsangabe
eine nicht geprüfte Kompatibilitätszusage abzuleiten.

Das Wiki ist aktuell eine schlanke Navigation zur versionierten Dokumentation.
Beim Audit waren seine beiden Seiten identisch mit `docs/wiki/`; eine zweite
vollständige Dokumentationskopie ist nicht nötig. Sinnvoll sind ein klarer
Einstieg für Anwender, Entwickler und Prüfer, eine kurze Startanleitung,
nachvollziehbare Release-Notizen sowie Link-/Befehlsprüfungen in CI. Historische
Messnachweise behalten Datum und Commit. Eine leere menschliche Abnahmevorlage
wird nicht durch automatisch erzeugte Erfolgsaussagen ausgefüllt.

## Funktionen mit fachlichem Mehrwert

Lauf- und Vergleichsfilter, Fallprofile, Ereignisdetails, Kampagnenvergleich,
Bewertungsfortschritt und Archivdownload sind bereits vorhanden. Nach dem
visuellen Paket bieten sich verständliche Kampagnennamen mit stabiler technischer
ID, optionale Tags und ein direkter CSV-Download der Vergleichsansicht an.
Ein Studienmanifest könnte die zugehörigen Kampagnen und eingefrorenen
Konfigurationen verknüpfen. Alle Darstellungen müssen weiterhin offene Urteile
und unvollständige Läufe unterscheiden.
Versionierte Bewertungsentwürfe bestehen bereits. Eine Ergänzung um
Konflikterkennung bei veralteten oder parallelen Änderungen ist nützlicher
als ein allgemeines Rollenverwaltungssystem für nur zwei bekannte Projektmitglieder.

Für den Modellpilot wäre ein Vorprüfungsdialog hilfreich: Fall-/Quellenfreigabe,
Modellstand, Umfang, Grenzen, geschätzte Kosten und Ausgabeziel. Er ersetzt keine
explizite Freigabe realer Aufrufe. Die UI erlaubt derzeit nur Mock-Kampagnen und
höchstens 480 Läufe; der geplante Hauptversuch umfasst vorläufig 720 Aufgabenläufe.
Das ist vor einer späteren UI-Anbindung bewusst zu lösen, etwa mit nachvollziehbar
verknüpften Teilkampagnen oder der vorhandenen CLI. Das UI-Limit wird nicht
unbemerkt erhöht. Paarbildung, Seeds, Belegidentität und Abbruchverhalten müssen
bei jeder Aufteilung erhalten bleiben.

Native Apps, Mehrmandantenbetrieb, neue Agententools, zusätzliche Modelle,
Live-Zusammenarbeit und umfangreiche Offline-Synchronisation werden zurückgestellt,
solange sie keinen konkreten Beitrag zum vereinbarten Untersuchungsziel leisten.

## Quellen und Ausgangsnachweise

- Repository: [Architektur](architecture.md), [Versuchsplan](experiment.md),
  [Betrieb](hosting.md), [Anmeldung](github-login.md), [Prüfstand](validation.md),
  [Sonar-Inventur](sonar-inventory.md), [Windows-Setup](setup-windows.md).
- [React Native Komponenten](https://reactnative.dev/docs/intro-react-native-components)
  und [native Knoten](https://reactnative.dev/docs/nodes).
- [MDN zu prefers-color-scheme](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-color-scheme)
  und [color-scheme](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/color-scheme).
- [SQLite Einsatzbereiche und Schreibkonkurrenz](https://sqlite.org/whentouse.html).
- [SQLite Online Backup](https://sqlite.org/backup.html).
- [Render Persistent Disks](https://render.com/docs/disks).
- [Playwright Barrierefreiheitsprüfungen](https://playwright.dev/docs/accessibility-testing).

Dieser Plan wurde mit ChatGPT/Codex aus Code, CI-Nachweisen, Anbieterinformationen
und den vorhandenen Konzeptunterlagen abgeleitet und unabhängig gegengeprüft.
Er erzeugt keine menschlichen Bewertungen oder empirischen Modellbefunde.
