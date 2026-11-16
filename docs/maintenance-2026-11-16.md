# Wartung und Befundabgleich vom 16. November 2026

## Ausgangsstand und bereits abgeschlossener Rollout

Diese Etappe setzt auf `7a4c436ec70952c67de81a19e64b4f0deedca369` auf.
[PR #46](https://github.com/sxba-04/llm-agent-security-lab/pull/46)
aktualisierte OpenTelemetry auf 1.45.2. Der vorherige vollständige Workspace
wurde extern gesichert, getrennt wiederhergestellt und mit dem Live-Inventar
verglichen, bevor der PR gemergt wurde. Pages und Render veröffentlichten den
Merge-Commit; Render-Deployment `dep-dbtj6n3tqb8s73c5cspg` wurde am
16.11.2026 um 17:47:19 Uhr MEZ live.

Auch nach dem Rollout wurden Export und getrenntes Restore geprüft. Alle
249 Workspace-Dateien (4.368.013 Bytes) waren vor und nach dem Deployment
pfad- und bytegleich. Beide Mock-Kampagnen (96/96 und 8/8), die bestätigte
vierseitige PDF und die ursprüngliche Bewertungsprovenienz blieben erhalten.

| Originalexport | SHA256 |
|---|---|
| Vor PR46 | `ba8822e6b9f5cc5f7277312dad8a196a78d1754f0a2fa915c5d83e72d368c560` |
| Nach PR46 | `8464bff9c5c17eca97a13f2fa8354768f1b9512f636b05a3318e2e86cf069eab` |

Der kanonische Workspace-Inventarhash beider Archive und Liveprüfungen lautet
`d19c403b8327900836d153086ad0e1d4eeadb876e2c319c84fa21872cc7a45c1`.
Die Originalarchive behalten `source_evidence_complete=false`, weil der
Hosting-Checkout zwei historische Kampagnen-Commits nicht enthält. Separat
gesicherte 58 aufgezeichnete Quell-/Lockdateien stimmen mit deren ursprünglicher
Kampagnenprovenienz und GitHub-Blobhashes überein; dies sind keine vollständigen
historischen Git-Trees. Das historische Archiv vom 10. November konnte in
dieser Sitzung nicht materialisiert werden. Ein Bytevergleich vom 10. zum
16. November wird deshalb weiterhin nicht behauptet.

Die vollständigen Originale, Inventare und Restorebelege sind im externen Paket
`Sicherheitslabor_Sicherung_PR46_2026-11-16.zip` erhalten. Hashes belegen
Konsistenz, keine kryptografisch gesicherte Urheberschaft.

## Exportblocker: Dateimodus des CI-Hilfsskripts

Vor und nach PR46 war die einzige versionierte Checkoutabweichung auf Render
der Modus von `.github/scripts/prefer-ubuntu-archive.sh`: Git erwartete
`100644`, das Dateisystem zeigte `100755`. Der Inhalt blieb unverändert
(Git-Blob `e9e56e7b99d03281368c4453671ee6a77e9bc15f`). Deshalb verweigerte die
Gesamtsicherung zu Recht einen angeblich sauberen Quellsnapshot.

Die neue Korrektur versioniert das bestimmungsgemäß ausführbare Bash-Skript
als `100755`, ohne Inhaltsänderung. Die bestehenden CI-Aufrufe verwenden
bereits ausdrücklich `sudo bash`; das Produktionsstartkommando bleibt gleich.
Es wird weder `core.filemode` deaktiviert noch eine Abweichung aus dem
Backup-Gate ausgeschlossen. Der verursachende Plattformschritt ist nicht
nachgewiesen. Die dauerhafte Wirkung muss nach dem Deployment durch einen
sauberen Gitstatus und regulären Export **ohne manuelle Moduskorrektur**
bestätigt werden; der PR-Abschlussnachweis hält dieses Ergebnis fest.

## Sechs konkrete Sonar-Befunde auf der Ausgangsrevision

Die angemeldete Sonar-Ansicht zeigte sechs offene Befunde auf `main`, davon
zwei mit Security-Auswirkung. Ein grünes Quality Gate ist kein Nachweis, dass
solche Altbefunde nicht existieren. Die aktuellen Fundstellen und historischen
Einzelbewertungen wurden unabhängig gegengeprüft. Die ursprünglichen Ledger
unter [sonar-triage](sonar-triage/README.md) bleiben unverändert.

| Issue-ID | Regel / Ausgangsposition | Beurteilung und Behandlung |
|---|---|---|
| `AaGMS_857rRJBvbBA1n8` | `python:S8392`, `hosted_cli.py:54` | Geprüfte beabsichtigte Nutzung: `0.0.0.0` gehört zum ausdrücklich genehmigten Render-Webbetrieb hinter HTTPS-Proxy, mit zwingender Hosted-Authentifizierung und Host-/Origin-Grenzen. Der lokale Launcher bleibt auf Loopback. Kein fehlendes Konstrukt und keine neue Freigabe von Exposition oder Modellisolierung. |
| `AaGMS_9e7rRJBvbBA1op` | `python:S4830`, `providers.py:91` | False Positive: der tatsächlich verwendete `ssl.create_default_context()` verlangt Zertifikats- und Hostnamenprüfung. Der bestehende Offline-Regressionstest prüft den übergebenen Kontext, Zertifikatsfehler, ausbleibende Wiederholung, bereinigte Fehler und erhaltene Kostenreservierung. Keine Provideränderung notwendig. |
| `AaGMS_9U7rRJBvbBA1oa` | `python:S2201`, `batch.py:359` | Strikte UTF-8-Validierung mit absichtlich ungenutztem Rückgabewert. Kommentar und explizite Zuweisung an `_` verdeutlichen die Absicht; Originalbytes, Hashes und Ablehnung ungültiger Bytes bleiben erhalten. Bereits vorhandener negativer Archivtest deckt neu berechnete Hashes bei ungültigem UTF-8 ab. |
| `AaHFOS7qq39aP6yr0hrs` | Lifespan-Cleanup, `server.py:705` | Echter Fehlerpfad: Cleanup hinter `yield` konnte bei einer Ausnahme ausfallen. `try/finally` garantiert den Shutdown. Die neue Regression prüft Ausnahme und Cancellation sowie unveränderte Weitergabe der ursprünglichen Ausnahme. |
| `AaHAaQo1X42v210R0gnu` | `python:S5655`, `luna_pilot.py:108` | Kontextueller Typ-Fehlalarm: `FirstTicketModel` erfüllt das strukturelle `Model`-Protokoll einschließlich `name`, `is_mock` und `respond`. Keine künstliche Vererbung, Casts oder Lockerung der Laufzeitschranken. Bestehende Pilot-Fixtures prüfen den gemeinsamen Ausführungspfad ohne echte API. |
| `AaGMS_7E7rRJBvbBA1l2` | veraltetes `returnValue`, `frontend/src/api.ts:215` | Sebastian entschied am 16.11.2026 für die aktuelle und vorherige stabile Version von Chrome, Edge, Firefox und Safari. Der Legacy-Zusatz entfällt zugunsten von `preventDefault()` mit tatsächlicher Browserregression. Supportentscheidung und Grenzen stehen in [browser-quality.md](browser-quality.md). |

Konkrete Remote-Dispositionen werden im zugehörigen PR mit Zeitpunkt und
Begründung festgehalten; die Tabelle allein behauptet keine bereits geänderten
Sonar-Statuswerte. Der Hosted-Befund ist eine beabsichtigte Verwendung, kein
TLS-Fehlalarm. Es werden keine Regeln, Dateien oder Datenflüsse ausgeschlossen.

## Prüfung und wissenschaftliche Grenzen

Die Arbeitskopie wurde aus dem verifizierten Quellsnapshot aufgebaut und alle
227 Gitblobhashes gegen den vollständigen GitHub-Tree geprüft. Ihr lokaler
Baselinecommit ist ein technischer Arbeitscommit, nicht die originale Main-SHA;
sein Tree ist exakt `818f5ab1c51ec873830ef5d24c3cb3ff9d27b712`.

Lokal verfügbar: Windows 11, Python 3.12.14, pypdf 6.21.4. Web-/Dev-Extras,
uv und die Frontendabhängigkeiten fehlen; ein Locked-Environment wird nicht
behauptet. Zwei bestehende TLS-/Redirecttests und zwölf Batchtests bestanden.
Webtests waren hier übersprungen. Pilot-/Archivtests stießen vor den geprüften
Transport-/UTF8-Schritten auf verweigerte Hardlinks (`os.link`, WinError 5).
Diese lokalen Einschränkungen ersetzen keine erfolgreichen CI-Ergebnisse.
Die vollständige Locked-Installation, Linux-/Windows-Suite und tatsächliche
Ausführung der neuen Regressionen sind vor Merge erforderlich; endgültiger
Head, Testzahlen und Codex-Code-/Security-Reviews stehen im PR.

Die neue Unload-Regression wurde gezielt eingegrenzt: In den Linux-Läufen
[43940235159](https://github.com/sxba-04/llm-agent-security-lab/actions/runs/43940235159)
(`dd91538`) und
[43942134420](https://github.com/sxba-04/llm-agent-security-lab/actions/runs/43942134420)
(`499d6f3`) blieb bei WebKit 27.2 mit Playwright 1.65.0 das erwartete
`close`-Ereignis nach dem Speichern aus, jeweils auch im Wiederholungsversuch.
Die vorherigen Prüfungen auf Dialog, Abbruch, erhaltenen Entwurf, Speicherung und
dialogfreies Neuladen bestanden. Die Trennung der Schließversuche auf unabhängige
Seiten beseitigte den Fehler nicht; eine konkrete Browser- oder Anwendungsursache
ist damit nicht nachgewiesen. Der endgültige Test prüft für alle Engines denselben
vollständigen Dokumentwechsel: ungespeichert erscheint der Dialog und Abbrechen
erhält den Entwurf; gespeichert wird das Ziel ohne Dialog erreicht. Das echte
Abbrechen eines Tab-Schließversuchs bleibt separat geprüft. Ein erfolgreicher
physischer Tab-Abschluss des gespeicherten Stands wird nicht behauptet. Es gibt
keinen WebKit-Skip; der aktuelle CI-Lauf muss den eingegrenzten Ablauf bestätigen.

ChatGPT/Codex bereitete Code und Dokumentation vor. Unabhängige Agenten prüften
Ursache, Befundgrenzen und Änderungen. Das ist KI-gestützte Arbeit und keine
erfundene menschliche Autorenabnahme. B/F/P/FP, Originaldaten, Bewertung und
Pilotgrenzen bleiben unverändert. Keine kostenpflichtigen Modellaufrufe,
keine neuen Dienste und keine behauptete äußere Modellisolierung.

## Nachfolgende Wartung

Dependabot #42 und #43 enthalten inzwischen OpenTelemetry 1.45.2. #43 scheiterte
in einem Linux-Lauf bereits bei der Installation von `poppler-utils`; dies
belegt keinen pypdf-Kompatibilitätsfehler. #44 und #45 lagen beim Abgleich hinter
Main. Alle vier benötigen gesonderte aktuelle Reviews; übersprungene Sonar-
Analysen und neutrale unvollständige CodeQL-Auswertungen gelten nicht als
bestandene Sicherheitsprüfung. Empfohlene getrennte Folge: #42, #45, #44, dann
das pypdf-Majorupdate #43 mit überprüfter Extraktionsprovenienz.

## Primärquellen

- [Python SSL: sichere Standardkontexte](https://docs.python.org/3/library/ssl.html#ssl.create_default_context)
- [Render: Portbindung von Webservices](https://render.com/docs/web-services#port-binding)
- [MDN: beforeunload](https://developer.mozilla.org/en-US/docs/Web/API/Window/beforeunload_event)
