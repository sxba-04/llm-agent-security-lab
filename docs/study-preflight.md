# Studienmanifest und Pilotvorprüfung

Stand: 6. November 2026. `python -m security_lab.study` arbeitet offline. Es
plant, verknüpft und prüft vorhandene Belege. Kein Befehl dieses Moduls liest
einen API-Schlüssel, konstruiert ein Modell oder startet einen Versuch. Die
Weboberfläche bleibt bei Mock-Kampagnen und höchstens 480 Aufgabenläufen.

## Einen Vergleich einfrieren

Ein Plan enthält die vollständigen Fallfassungen, vier Varianten, beide Quellen,
Wiederholungen, Limits, Providerkonfiguration und Code-/Lockdatei-Fingerabdrücke.
Er ist eine **Vorbereitung**, keine Autorenfreigabe oder Hauptmessung. Den Plan
erst nach den beabsichtigten Codeänderungen erzeugen. Während der verknüpften
Serie keine Implementierung oder Lockdateien ändern.

```powershell
uv run --locked --extra web python -m security_lab.study plan --cases cases/dev --name "Entwicklung Mock-Abnahme" --repeats 1 --output runs/studies/mock-plan-v1.json
uv run --locked --extra web python -m security_lab.study preflight runs/studies/mock-plan-v1.json
uv run --locked --extra web python -m security_lab.study export-cases runs/studies/mock-plan-v1.json --part part-01 --output runs/studies/mock-cases-v1
uv run --locked --extra web python -m security_lab run --cases runs/studies/mock-cases-v1 --output runs/study-mock-v1 --repeats 1 --seed 20261022
uv run --locked --extra web python -m security_lab.study link runs/studies/mock-plan-v1.json --campaigns runs/study-mock-v1 --output runs/studies/mock-evidence-v1.json
uv run --locked --extra web python -m security_lab.study verify runs/studies/mock-plan-v1.json --evidence runs/studies/mock-evidence-v1.json --campaigns runs/study-mock-v1
```

Das Beispiel verwendet alle zwölf Entwicklungsfälle und erzeugt 96 Mock-Läufe.
Es ersetzt die fachliche [Abnahme mit drei Fällen und sechs PDFs](manual-acceptance.md)
nicht. Bereits vorhandene Zielverzeichnisse und Ausgabedateien werden nicht
überschrieben. Studienartefakte gehören in `studies/` des jeweiligen Workspace,
damit die vollständige [Workspace-Sicherung](workspace-backup.md) sie erfasst.
Der Sicherungsbefehl und seine endgültigen Dateinamen sind dort beschrieben.

`link` verwendet die gemeinsame Kampagnenprüfung: Originalaufzeichnungen,
Ereignisse, PDF-Originale/Extraktionen/Bestätigungen und Bewertungsprovenienz
werden geprüft. Zusätzlich bindet eine Dateiliste alle vorhandenen Kampagnendateien
einschließlich Metadaten und Entwurfshistorien an den Studiennachweis. Ein später
hinzugefügter oder geänderter Entwurf macht den alten Nachweis nicht falsch,
aber die aktuelle Verzeichnisfassung entspricht ihm nicht mehr. In diesem Fall
einen neuen Nachweis mit neuer Versionsdatei erzeugen; den alten erhalten.

Die Prüfung unterscheidet `verified_integrity`, `evidence_complete` und
`execution_complete`. Eine sauber erhaltene abgebrochene Kampagne kann integre
Teilbelege haben; sie wird dadurch nicht vollständig. Hashwerte beweisen keine
Urheberschaft, und `human_approval_verified` bleibt `false`.

## 720 geplante Läufe ohne Änderung der UI-Grenze

Ein Plan aus **30 separat freigegebenen Fallpaaren**, drei Wiederholungen und
acht Bedingungen umfasst 720 Aufgabenläufe. Bei 480 Läufen pro Teil entstehen
zwei Teile mit 20 beziehungsweise zehn Fällen, also 480 und 240 Läufen. Der
noch nicht freigegebene Haupttestkatalog wird durch dieses Werkzeug weder
erzeugt noch aus Entwicklungsfällen umetikettiert.

Jeder Fall bleibt mit allen Wiederholungen und Bedingungen in genau einem Teil.
Ein Fall-Wiederholungs-Paar wird niemals zwischen Kampagnen geteilt. Jeder Teil
hat einen im Plan gespeicherten Reihenfolge-Seed (`base_seed + Teilindex`, erster
Index null). Diese Teilrandomisierung ist reproduzierbar, aber **nicht identisch
mit der Reihenfolge einer ungeteilten 720er-Kampagne**. Sie muss vor der Messung
vereinbart werden. Der pro Kampagne erzeugte Fixture-Seed bleibt im jeweiligen
Originalmanifest und im Studiennachweis erhalten; es werden keine Daten
nachträglich zusammenkopiert oder lokale Laufkennungen neu vergeben.

Für jeden Teil `export-cases` mit dessen `part_id` ausführen. Anschließend die
vorhandene CLI mit genau den Wiederholungen, dem `order_seed`, den Limits und
der Providerkonfiguration des Plans verwenden. `link --campaigns` erwartet
genau einen Pfad pro Teil in Planreihenfolge. Ein falscher Fallstand, doppelte
Pfade, eine andere Reihenfolge oder abweichende Konfiguration werden abgelehnt.
Wiederhergestellte Kopien können unter neuen Pfadnamen mit `verify` geprüft
werden; sie werden nicht als zusätzliche Messung gezählt.

## Kosten und offene Freigaben sichtbar machen

Für eine geplante vergleichende Pilotserie kann `plan --api-config` eine
vollständig ausgefüllte, **schlüsselfreie** Konfiguration aus
`configs/api.example.json` übernehmen. Deren Platzhalter sind keine aktuellen
Preise oder Modellentscheidung. Die gemeinsame Providerprüfung lehnt unbekannte
Felder ab; Zugangsdaten gehören nicht in diese Datei.

```powershell
uv run --locked --extra web python -m security_lab.study plan --cases cases/dev --name "Vergleichender Pilot – Vorbereitung" --repeats 1 --api-config configs/api.local.json --output runs/studies/pilot-plan-v1.json
uv run --locked --extra web python -m security_lab.study preflight runs/studies/pilot-plan-v1.json --already-spent-eur 0
```

`0` ist hier ein Syntaxbeispiel: den tatsächlich abgeglichenen bisherigen
Projektverbrauch einsetzen. Die Vorprüfung weist pro Anfrage den Betrag aus
den konfigurierten Eingabe-/Ausgabelimits und Preisen sowie die maximal geplanten
Anfragen aus. Bei Teilkampagnen berücksichtigt sie, dass `max_requests` und
`run_budget_eur` pro CLI-Kampagne gelten. Die Summe dieser Teilbudgets plus der
angegebene Altverbrauch wird gegen 250 EUR geprüft. Fehlender Altverbrauch wird
als `unknown_spend` gemeldet. Die Anfragegrenze der vorhandenen CLI beträgt
1 EUR; eine zu große konfigurierte Reservierung wird sichtbar ausgewiesen.

Dies sind konfigurierte Schätzwerte, keine Preisprüfung, Rechnungsgarantie oder
globaler Abgleich anderer Rechner. Für echte Ausführung denselben persistenten
Budget-Ledger verwenden und dessen offene Reservierungen mit dem Anbieter
abgleichen. Ein kleiner erster Pilot nur mit sauberen B-Aufgaben bleibt ein
gesondert festgelegter Umfang der vorhandenen CLI; der Studienplan oben bildet
bewusst den vollständigen achtfachen Vergleich ab.

Die optionalen Parameter `--author-acceptance`, `--outer-isolation` und
`--external-restore` referenzieren tatsächlich vorhandene Protokolldateien. Die
Vorprüfung liest deren Hash, bewertet ihren Inhalt jedoch nicht: Status
`supplied_unverified` statt einer erfundenen Freigabe. Ohne Datei lautet der
Status `missing`. Ein gesetztes CLI-Flag stellt weiterhin keine äußere Isolation
her. `paid_run_authorized` und `main_experiment_approved` bleiben immer `false`.

Vor einer echten Ausführung bleiben konkret erforderlich:

1. Autoren prüfen Fälle, PDF-Texte und Rubrik anhand der unveränderten
   [Protokollvorlage](manual-acceptance-record-template.md).
2. Äußere Isolation und vollständige externe Sicherung samt Wiederherstellung
   werden separat nachgewiesen.
3. Modellstand, aktuelle Preise, Umfang, Abbruchgrenzen, Ledger und Ausgabeziel
   werden festgelegt; der konkrete kostenpflichtige Lauf wird ausdrücklich
   autorisiert.
4. Der Pilot liefert gemessene Verbräuche und die menschlich geprüfte Reifeprüfung
   aus dem [Versuchsplan](experiment.md). Erst danach folgt die Haupttestfreigabe.

Automatisierte Tests dieser Erweiterung verwenden ausschließlich Mock-Daten
und erfundene Testpreise. Die Umsetzung wurde mit Codex unterstützt; sie erzeugt
keine menschlichen Urteile oder empirischen LLM-Ergebnisse.
