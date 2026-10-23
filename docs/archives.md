# Kampagnen sichern und wiederherstellen

Eine Kampagne besteht aus Manifest, Fallsnapshot, ursprünglichen Einzelläufen und Ereignisprotokollen. Innerhalb der Kampagne abgelegte PDF-Quellen und Bewertungsdateien gehören ebenfalls dazu. `runs/` wird nicht von Git versioniert; ein Commit allein sichert daher keine Messdaten.

## CLI

```powershell
uv run python -m security_lab archive runs/pilot --output runs/pilot-v1.zip
uv run python -m security_lab verify-archive runs/pilot-v1.zip
uv run python -m security_lab restore-archive runs/pilot-v1.zip --output runs/restored-pilot
uv run python -m security_lab summarize runs/restored-pilot --output runs/restored-pilot/recomputed.json
```

Ausgabe-ZIP und Wiederherstellungsordner müssen neu sein. Das ZIP liegt außerhalb der ursprünglichen Kampagne. Aktive Kampagnen werden nicht exportiert. Ein Archiv enthält ein Inhaltsverzeichnis mit Dateigrößen und SHA-256-Hashes. Die Prüfung umfasst jeden Eintrag sowie den Zusammenhang zwischen Manifest, Laufdatensätzen und Ereignissen. Archivpfade, Größen und Eintragszahlen werden begrenzt; Links und Pfadwechsel außerhalb des Zielverzeichnisses werden zurückgewiesen.

Bei einer Wiederherstellung wird auch das ursprüngliche ZIP unter `provenance/` bewahrt. Ableitungen wie eine neue Zusammenfassung dürfen neu erzeugt werden; Originalnachweise werden nicht ersetzt.

Der kanonische Laufdatensatz wird vor seinem zusätzlichen JSONL-Ereignisprotokoll dauerhaft indexiert. Scheitert anschließend das Schreiben dieses Protokolls, bleibt der Datensatz einschließlich seiner Ereignisse erhalten und die Serie wird als unterbrochen markiert. Ein solches Archiv meldet `evidence_complete: false` und listet fehlende Ereignisdateien auf. `verified_integrity: true` bestätigt nur die Konsistenz der vorhandenen Dateien; es darf nicht als Vollständigkeitsnachweis gelesen werden. Bereits vorhandene, beschädigte Ereignisdateien werden weiterhin zurückgewiesen. PDF-Quellen und Review-Pakete werden zusätzlich gegen die konkreten Laufdatensätze geprüft.

## GUI und menschliche Bewertungen

Der Archivdownload einer UI-Kampagne schließt ihre zugeordneten PDF-Belege und dort gespeicherten Review-Versionen ein. Wer die CLI-Bewertung außerhalb des Kampagnenverzeichnisses ablegt, muss dieses Verzeichnis separat sichern oder unter `reviews/` der Kampagne aufbewahren. Die ursprünglichen Exportpakete, beide Einzelbewertungen und alle begründeten Klärungen gehören zur Reproduktion.

## Was die Prüfung aussagt

Hashes prüfen Konsistenz gegenüber dem archivierten Inhaltsverzeichnis. Sie beweisen weder Urheberschaft noch, dass ein Angreifer mit Schreibzugriff nicht Dateien und Inhaltsverzeichnis gemeinsam ersetzt hat. Es handelt sich nicht um eine digitale Signatur.

Der Quellcode wird nicht automatisch in jedes Laufarchiv kopiert. Zusätzlich müssen der im Manifest genannte Git-Commit einschließlich Lockdateien sowie die dokumentierten Startbefehle verfügbar bleiben. Für die digitale Studienarbeitsanlage werden deshalb **Codearchiv des eingefrorenen Commits und Kampagnenarchive gemeinsam** abgegeben. Der Exportbericht benennt diesen Umfang ausdrücklich.
