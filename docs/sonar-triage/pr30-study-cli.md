# PR 30: Einzelprüfung der Study-/Scanner-Pfadwarnungen

Statische Prüfung der drei unten genannten Sonar-Annotationen gegen den
gemeldeten Stand `6b48f567e708de55230029549fee7a27c06b3d93`.
Die Annotationen enthalten Titel, Datei, Zeile und Issue-Link, aber keinen
Angriffspfad oder PoC (`raw_details: null`). Die Zeilenangaben beziehen sich
auf diesen Commit; spätere Änderungen der Metrikparser sind nicht Teil der
hier bewerteten Pfadoperationen.

| Sonar-Issue | Gemeldete Stelle | Einzelurteil | Sicherheit des Urteils |
| --- | --- | --- | --- |
| [AaGwHoBJ3f6_aqzNEjCV](https://sonarcloud.io/project/issues?id=sxba-04_llm-agent-security-lab&issues=AaGwHoBJ3f6_aqzNEjCV&pullRequest=30) | `study.export_part_cases`, `study.py:127` | `not_actionable`: behaupteter LLM→CLI-Pfad nicht vorhanden | hoch |
| [AaGwHoBJ3f6_aqzNEjCW](https://sonarcloud.io/project/issues?id=sxba-04_llm-agent-security-lab&issues=AaGwHoBJ3f6_aqzNEjCW&pullRequest=30) | `study._read_json`, `study.py:41` | `not_actionable`: gelesener Pfad stammt vom Operator | hoch |
| [AaGwHoBb3f6_aqzNEjCY](https://sonarcloud.io/project/issues?id=sxba-04_llm-agent-security-lab&issues=AaGwHoBb3f6_aqzNEjCY&pullRequest=30) | `sonar_inventory.scanner_submission`, `sonar_inventory.py:190–191` | `not_actionable`: fester CI-Pfad oder lokales Operatorargument | hoch |

Dies sind lokale, einzeln begründete Triage-Ergebnisse, keine Änderungen des
Sonar-Status und keine pauschale Ausnahme für CLI-Code. Es wurde weder ein
Quality Gate abgeschwächt noch eine Regel unterdrückt. Es wird kein erfolgreich
ausgeführter Exploit behauptet; diese Prüfung verwendet statische Datenflüsse.

## Gemeinsame Grenze: Was das Modell tatsächlich aufrufen kann

Die Befundtitel behaupten jeweils „Path Traversal via faulty LLM-supplied CLI
arguments“. Dafür müsste untrusted Artikel-/PDF- oder Modellinhalt zuerst
Autorität über die Host-CLI erlangen. Der konkrete Gegenbeleg im geprüften
Stand ist:

- [`core.py:33–43`](https://github.com/sxba-04/llm-agent-security-lab/blob/6b48f567e708de55230029549fee7a27c06b3d93/src/security_lab/core.py#L33)
  definiert ausschließlich `read_ticket` und `append_note`. `respond()` erhält
  genau diese Tool-Schemata (`core.py:248`).
- `_syntax_error()` (`core.py:88–105`) weist unbekannte Toolnamen und zusätzliche
  Argumentfelder zurück; Ticket-IDs müssen dem eingeschränkten Muster
  entsprechen und bereits in den synthetischen Tickets existieren.
- `gateway()` (`core.py:181–215`) prüft diese Syntax in **allen** Bedingungen.
  Die Effekte sind eine Kopie eines In-Memory-Tickets oder das Anhängen eines
  Texts an dessen Notizliste. Der Notiztext wird weder als Pfad noch als
  Shellkommando ausgewertet. B/F schalten diese Infrastrukturkontrollen nicht ab.
- Die registrierten HTTP-Routen (`server.py:214–238`) stellen weder das
  Study-CLI noch `scanner_submission()` bereit. Die drei geprüften Funktionen
  werden nicht aus der Modell-Toolausführung aufgerufen.

Dies entspricht den überprüften Grenzen in [SECURITY.md](../../SECURITY.md):
Artikel, PDF, Modellantworten und Toolargumente sind untrusted; Operatoren mit
demselben Betriebssystemkonto sind keine voneinander isolierten Mandanten.
Entscheidend ist der konkrete fehlende Übergang, nicht allein die Bezeichnung
„lokal“ oder „CLI“.

## AaGwHoBJ3f6_aqzNEjCV — Export der Fallpartition

**Datenfluss:** Operator-`argv` → `_parser()` (`study.py:277–303`, `--output`
als `Path`) → `_run_command()` (`study.py:314–316`) →
`export_part_cases(plan, args.part, args.output)` →
`output.mkdir(parents=True, exist_ok=False)` (`study.py:127`).

Vor dem Anlegen validiert `validate_plan()` das eingefrorene Schema, die Fälle,
Partitionen, Seeds und Fingerprints; anschließend muss `part_id` einer
berechneten Partition entsprechen (`study.py:89–129`). Der vom Operator
ausgewählte Zielordner muss neu sein. Die Dateinamen werden ausschließlich aus
einem lokalen Zähler gebildet (`case-001.json` usw.); weder `case_id`, Studientitel
noch Artikel-/Modelltext werden zu Dateinamen. `write_json_new()`
(`batch.py:66–89`) veröffentlicht vollständige JSON-Dateien mittels exklusiver
Temporärdatei und Hardlink ohne Überschreiben eines bestehenden Ziels.

**Gegenbeispiel zur behaupteten Kontrolle:** Ein Artikel mit einer Anweisung
`--output ../../outside` kann als Text im Fall stehen, setzt aber nicht
`args.output`. Selbst ein Modell-Toolaufruf namens `export-cases` scheitert als
`unknown_tool`, bevor ein Effekt eintritt. Ein Operator kann dagegen bewusst
einen neuen Ordner außerhalb des Repositorys wählen. Das ist die vorgesehene
Exportfunktion mit den Dateirechten dieses Operators, kein aus Modellinhalt
erreichbarer Rechtewechsel.

**Grenze und nächste Maßnahme:** Es gibt hier absichtlich keine Beschränkung
auf das Web-Workspace-Verzeichnis. Die Operation beansprucht keine Isolation
gegen einen konkurrierenden Prozess desselben OS-Kontos, der Verzeichnisse
austauscht. Für eine zukünftige HTTP-/Modell-Tool-Anbindung wären eine eigene
Autorisierung, verwaltete Ziele und eine erneute Pfadprüfung erforderlich.
Für den gemeldeten Stand ist kein Sicherheitsfix dieses Befunds begründet.

## AaGwHoBJ3f6_aqzNEjCW — Lesen der Study-JSON-Eingaben

**Datenfluss:** Operator-`argv` → `Path`-Argumente → `_run_command()` →
`_read_json(args.api_config)` (`study.py:308`), `_read_json(args.plan)`
(`study.py:314`) beziehungsweise `_read_json(args.evidence)` (`study.py:323`)
→ `path.read_text(encoding="utf-8")` (`study.py:41`). Beim Verknüpfen von
Kampagnen kommt zusätzlich `directory / "manifest.json"` aus den ausdrücklich
übergebenen `--campaigns`-Verzeichnissen hinzu (`study.py:146–148`). Ein JSON-
Feld oder ein Modellargument wird nicht als Ersatz für diese Lesepfade benutzt.

`_read_json()` (`study.py:29–44`) lehnt einen Symlink als letzte Pfadkomponente,
nichtreguläre Dateien und vor dem Lesen Dateien über 16 MiB ab. Doppelte
JSON-Schlüssel, nichtendliche Zahlen und andere oberste JSON-Typen als Objekte
werden zurückgewiesen. Diese Prüfungen dienen der Eingabevalidität; sie sind
**keine** vollständige Root-Confinement- oder TOCTOU-Abwehr.

**Gegenbeispiel zur behaupteten Kontrolle:** Ein Textfeld mit `/etc/passwd`
oder `../../private.json` bleibt JSON-Inhalt; `_read_json()` folgt daraus keiner
weiteren Dateireferenz. Eine gezielte Pfadwahl ist nur über die bereits
privilegierten Operatorargumente möglich. Die Ausgabe enthält nicht einfach
den beliebigen Rohinhalt der Eingabedatei; weitere Schritte prüfen das jeweils
erwartete Plan-/Konfigurations-/Evidenzschema.

**Grenze und nächste Maßnahme:** Elternverzeichnis-Symlinks und Änderungen
zwischen `stat()` und `read_text()` sind nicht vollständig ausgeschlossen.
Ein solcher Angriff benötigt hier Kontrolle über das vom Operator verwendete
Host-Dateisystem; der behauptete LLM-Einstieg dafür fehlt. Keine pauschale
Freigabe für zukünftige Aufrufer: Ein neu ergänzter untrusted Pfadparameter
oder automatische Ausführung fremder CLI-Vorschläge wäre erneut zu prüfen.

## AaGwHoBb3f6_aqzNEjCY — Scanner-Einreichungsbeleg

**Datenfluss in CI:** Der geschützte Diagnose-Schritt in
[`sonar.yml:89–100`](https://github.com/sxba-04/llm-agent-security-lab/blob/6b48f567e708de55230029549fee7a27c06b3d93/.github/workflows/sonar.yml#L89)
übergibt den literalen Pfad `--scanner-report .scannerwork/report-task.txt`.
Er läuft nur für PRs aus demselben Repository, nicht für Dependabot, nach einem
Scanner-Schritt und bei vorhandenem Beleg. Weder PR-Titel noch Modelltext
bestimmen diesen Pfad. Lokal gilt `--scanner-report` als explizites
`argparse`-`Path`-Argument; `collect()` reicht dieses an
`scanner_submission()` weiter. Die Lesesenke ist `path.open("rb")`.

**Kontrollen und Auswirkungen:** `scanner_submission()` liest höchstens
32.769 Bytes und lehnt mehr als 32.768 Bytes sowie ungültiges UTF-8 ab. Nur
`projectKey`, `serverUrl` und `ceTaskId` werden ausgewertet; doppelte ausgewählte
Felder führen zum Fehler. Projekt und Server müssen den fest konfigurierten
Werten entsprechen. Die einzige variable veröffentlichte Beleginformation ist
eine Task-ID nach `[a-zA-Z0-9_-]{1,200}`. Unbekannte Felder, URLs und Rohinhalt
werden nicht übernommen. Der Rückgabewert bezeichnet den Beleg ausdrücklich
als lokale Einreichung, nicht als serverseitig bestätigte Analyse.

**Gegenbeispiel zur behaupteten Kontrolle:** Ein fremder `serverUrl`-Wert
führt zum Fehler; er wird nicht zur Netzwerkadresse. `SonarClient` verwendet
den konstanten HTTPS-Host und eine Endpoint-Allowlist. Ein Artikel mit einem
Dateipfad gelangt weder zu `args.scanner_report` noch in den CI-Befehl. Ein
lokaler Operator mit eigenen Dateirechten kann das Argument ändern; daraus
entsteht noch kein LLM-gesteuerter Lesezugriff oder Rohdatenexport.

**Grenze und nächste Maßnahme:** Der Parser ist kein allgemeiner Dateisandbox-
Dienst. Die Vertrauensannahme für ausführbaren Repository-Code und CI-Secrets
muss erhalten bleiben; untrusted Fork-Code darf diesen Schritt nicht mit
Secrets ausführen. Eine spätere Weitergabe von Modell-/HTTP-Pfaden wäre ein
anderer Aufrufweg und neu zu prüfen. Kein begründeter Fix oder Remote-
Statuswechsel für die vorliegende Meldung.

## Nachvollziehbarkeit und verbleibende Beweislücke

Vorhandene Regressionen dokumentieren zusätzlich die beabsichtigte Semantik:
`test_frozen_case_export_is_readable_and_never_overwrites`,
`test_cli_refuses_overwriting_plan_and_campaign` und
`test_cli_mock_preflight_and_duplicate_json_failure` in `tests/test_study.py`
sowie `test_scanner_receipt_is_bounded_and_exports_only_validated_task_identifier`
in `tests/test_sonar_inventory.py`. Sie wurden für diese statische Triage nicht
erneut ausgeführt; ihr Vorhandensein ersetzt nicht den geprüften Datenfluss.

Die drei Annotationen liefern keinen konkreten niedrig privilegierten Aufrufer,
der die genannten Pfade ändern kann. Ein nachgereichter solcher Aufrufweg,
ein neuer Tool-/HTTP-Einstieg oder eine Änderung der Deployment-Grenzen würde
die jeweilige Bewertung wieder öffnen. Die separat gemeldeten Backup-,
Archiv- und Doctor-Stellen werden hier weder bewertet noch mitgeschlossen.
