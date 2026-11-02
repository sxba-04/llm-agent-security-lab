# Kampagnen sichern und wiederherstellen

Eine Kampagne besteht aus Manifest, Fallsnapshot, ursprünglichen Einzelläufen und Ereignisprotokollen. Innerhalb der Kampagne abgelegte PDF-Quellen und Bewertungsdateien gehören ebenfalls dazu. `runs/` wird nicht von Git versioniert; ein Commit allein sichert daher keine Messdaten.

## Regelmäßige Sicherung der kostenlosen Demo

Als Sicherungsweg wurden am 1. November 2026 **lokale Archive** gewählt: versionierte ZIP-Downloads auf den eigenen Rechner mit Archivprüfung und probeweiser Wiederherstellung. Dafür wird kein zusätzlicher Dienst gebucht. Der Render-Workspace ist flüchtig: Ein Ruhezustand, Neustart oder Deployment kann seine Dateien löschen. Ein Export im selben Workspace schützt davor nicht. Die folgende manuelle Routine gilt für jede benötigte Kampagne einzeln:

1. Sobald ein Versuch beendet ist, unter **Versuche → Versuch öffnen → Archiv herunterladen** das ZIP in einem dauerhaft aufbewahrten lokalen Archivordner auf dem eigenen Rechner speichern. Ein abgebrochener Versuch kann ebenfalls gesichert werden; sein tatsächlicher Status bleibt erhalten.
2. Nach gespeicherten Bewertungsentwürfen, abgeschlossenen Doppelbewertungen und Klärungen erneut exportieren. Jedes ZIP ist eine Momentaufnahme; frühere Downloads enthalten spätere Änderungen nicht. Für jeden Stand einen neuen Dateinamen verwenden, beispielsweise `kampagne-2026-11-01-v2.zip`, und ältere Belege behalten.
3. Vor Arbeitsende und vor geplanten Backend-Updates prüfen, ob von jeder wichtigen Kampagne der letzte Stand heruntergeladen wurde. Auf einen späteren Tages- oder Wochenlauf allein lässt sich bei einem flüchtigen Dienst nicht vertrauen.
4. Den heruntergeladenen Stand mit `verify-archive` prüfen und mindestens einmal in einen neuen Ordner wiederherstellen, wie unten gezeigt. `verified_integrity` und `evidence_complete` getrennt prüfen. Fehlende oder beschädigte Belege lassen sich durch erneuten Export oder Wiederholen eines Versuchs nicht als ursprüngliche Belege ersetzen.
5. Die geprüften ZIP-Dateien mit ihren Versionsständen im lokalen Archivordner behalten. Separat hochgeladene, noch keiner Kampagne zugeordnete PDF-Originale und das passende Codearchiv ebenfalls außerhalb der Demo aufbewahren.

Die Sicherung erfolgt durch den tatsächlichen Download und die lokale Prüfung; ein geplanter Export auf dem Render-Server würde weiterhin im flüchtigen Speicher liegen. Ein automatischer Fern-Backupdienst ist nicht eingerichtet. Zugangscodes und Modellschlüssel gehören weder in ein Exportskript noch in ein öffentliches Repository. Archivdateien können unverblindete Laufdaten, Zuordnungen und Originalbewertungen enthalten; die organisatorische Trennung der Bewertungen gilt auch für ihre lokale Ablage.

## CLI

```powershell
uv run python -m security_lab archive runs/pilot --output runs/pilot-v1.zip
uv run python -m security_lab verify-archive runs/pilot-v1.zip
uv run python -m security_lab restore-archive runs/pilot-v1.zip --output runs/restored-pilot
uv run python -m security_lab summarize runs/restored-pilot --output runs/restored-pilot/recomputed.json
```

Ausgabe-ZIP und Wiederherstellungsordner müssen neu sein. Das ZIP liegt außerhalb der ursprünglichen Kampagne. Aktive Kampagnen werden nicht exportiert. Ein Archiv enthält ein Inhaltsverzeichnis mit Dateigrößen und SHA-256-Hashes. Die Prüfung umfasst jeden Eintrag sowie den Zusammenhang zwischen Manifest, Laufdatensätzen und Ereignissen. Archivpfade, Größen und Eintragszahlen werden begrenzt; Links und Pfadwechsel außerhalb des Zielverzeichnisses werden zurückgewiesen.

Das Export-ZIP wird zuerst vollständig geschrieben, geprüft und synchronisiert. Erst dann wird es unter seinem endgültigen Namen veröffentlicht, ohne ein vorhandenes Ziel zu überschreiben. Dazu muss das Zieldateisystem Hardlinks unterstützen, etwa NTFS oder die üblichen Linux-Dateisysteme. Auf anderen Dateisystemen schlägt die Veröffentlichung sicher fehl; zunächst auf ein unterstütztes lokales Dateisystem exportieren und das fertige ZIP anschließend kopieren und erneut prüfen. Ein harter Prozessabbruch kann eine temporäre `.campaign-*.zip` hinterlassen; diese Datei ist kein bestätigter Export.

Bei einer Wiederherstellung wird auch das ursprüngliche ZIP unter `provenance/` bewahrt. Ableitungen wie eine neue Zusammenfassung dürfen neu erzeugt werden; Originalnachweise werden nicht ersetzt.

Der kanonische Laufdatensatz wird vor seinem zusätzlichen JSONL-Ereignisprotokoll dauerhaft indexiert. Scheitert anschließend das Schreiben dieses Protokolls, bleibt der Datensatz einschließlich seiner Ereignisse erhalten und die Serie wird als unterbrochen markiert. Ein solches Archiv meldet `evidence_complete: false` und listet fehlende Ereignisdateien auf. `verified_integrity: true` bestätigt nur die Konsistenz der vorhandenen Dateien; es darf nicht als Vollständigkeitsnachweis gelesen werden. Bereits vorhandene, beschädigte Ereignisdateien werden weiterhin zurückgewiesen. PDF-Quellen und Review-Pakete werden zusätzlich gegen die konkreten Laufdatensätze geprüft.

## GUI und menschliche Bewertungen

Der Archivdownload einer UI-Kampagne schließt ihre zugeordneten PDF-Belege und dort gespeicherten Review-Versionen ein. Wer die CLI-Bewertung außerhalb des Kampagnenverzeichnisses ablegt, muss dieses Verzeichnis separat sichern oder unter `reviews/` der Kampagne aufbewahren. Die ursprünglichen Exportpakete, beide Einzelbewertungen und alle begründeten Klärungen gehören zur Reproduktion. Abgeschlossene Bewertungsdateien werden gegen die tatsächlich archivierten Pakete, Zuordnungen und ursprünglichen CSV-Dateien geprüft. Jede Klärung muss ihren Vorgänger enthalten und ausschließlich die dokumentierte Abweichung auflösen. Die Prüfung meldet die erkannten Versionen unter `verified_review_versions`. Unfertige Einzelbewertungen dürfen als Entwürfe archiviert werden; eine abgeschlossene Zusammenführung ohne ihre Originaleingaben oder Vorgängerversionen wird zurückgewiesen. Kombinierte und geklärte Bewertungen werden mit der Dateiendung `.json` gespeichert; die CLI verlangt diese Endung. JSON-Dateien müssen lesbar und einer unterstützten Kampagnenrolle zuordenbar sein. Unbekannte JSON-Dateien werden mit einer Fehlermeldung abgelehnt, damit eine beschädigte Bewertungsdatei mit frei gewähltem Namen nicht unbemerkt als sonstige Anlage gilt. Unabhängige Notizen und fremde JSON-Dateien deshalb außerhalb der Kampagne aufbewahren; sonstige Nicht-JSON-Anlagen sind nur durch ihren Dateihash geprüft.

Nach dem Wiederherstellen unter einem neuen Ordnernamen erhält die Kampagne eine aktuelle lokale Kennung. Die Oberfläche ordnet ihre Bewertungen anhand des enthaltenen Verzeichnisses und der verifizierten Laufhashes zu. Bei Kopien verwendet sie eine eindeutige, vom Speicherort abgeleitete API-Kennung; ursprüngliche Kampagnen- und Bewertungskennungen bleiben als Herkunftsfelder erhalten. Keine archivierte Metadatendatei wird dafür umgeschrieben. Original und wiederhergestellte Kopie können nebeneinander geöffnet werden.

Unvollständige oder beschädigte Bewertungssätze erscheinen getrennt mit Fehlermeldung und bleiben von Bewertung und Vergleich ausgeschlossen. Gesunde Sätze bleiben erreichbar; Teildateien werden nicht stillschweigend gelöscht. Ein solcher Hinweis ist kein erfolgreich verifiziertes Archiv.

## Was die Prüfung aussagt

Hashes prüfen Konsistenz gegenüber dem archivierten Inhaltsverzeichnis. Sie beweisen weder Urheberschaft noch, dass ein Angreifer mit Schreibzugriff nicht Dateien und Inhaltsverzeichnis gemeinsam ersetzt hat. Es handelt sich nicht um eine digitale Signatur.

Der Quellcode wird nicht automatisch in jedes Laufarchiv kopiert. Zusätzlich müssen der im Manifest genannte Git-Commit einschließlich Lockdateien sowie die dokumentierten Startbefehle verfügbar bleiben. Für die digitale Studienarbeitsanlage werden deshalb **Codearchiv des eingefrorenen Commits und Kampagnenarchive gemeinsam** abgegeben. Der Exportbericht benennt diesen Umfang ausdrücklich.
