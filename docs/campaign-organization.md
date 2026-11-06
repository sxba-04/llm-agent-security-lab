# Versuche organisieren, vergleichen und gemeinsam bewerten

Stand: 6. November 2026. KI-unterstützte Implementierung; Mock-Prüfungen sind
technische Nachweise und keine empirischen LLM-Ergebnisse oder Autorenurteile.

## Namen und Tags

Ein optionaler Versuchsname und bis zu zwölf Tags lassen sich beim Start eines
Mock-Versuchs angeben. Nach dem Abschluss können sie in der Detailansicht unter
„Versuchsname und Tags bearbeiten“ geändert werden. Die technische Kampagnen-ID,
Konfiguration, Reihenfolge, Originalprotokolle und Bedingungen B/F/P/FP bleiben
unverändert. Ein Name ist keine Freigabe und kein wissenschaftliches Urteil.

Jede Änderung erzeugt eine neue kanonische Datei unter
`campaign-metadata/metadata-NNNNNN.json`, Schema 1. Sie enthält Name, Tags,
Revision, UTC-Zeitstempel und die SHA-256-Prüfsumme der vorherigen Datei. Alte
Kampagnen ohne diese Dateien beginnen mit Revision 0. Ein unbekanntes Schema,
Lücken, doppelte JSON-Felder, ungültige Zeichen oder veränderte Vorgängerversionen
werden abgelehnt. Archivexport und Wiederherstellung prüfen und erhalten die
vollständige Historie. Hashes belegen Konsistenz, keine Urheberschaft; sie können
insbesondere kein Löschen eines gesamten Historienendes ohne externen Vergleich
beweisen. Externe Sicherungen bleiben erforderlich.

Änderungen senden die zuvor gelesene Revision. Eine veraltete Änderung erhält
HTTP 409 und schreibt keine neue Datei. Erst nach dem bewussten Laden des
aktuellen Stands kann erneut gespeichert werden. Im unterstützten einzelnen
Serverprozess sehen Leser keine unfertige atomare Veröffentlichung. Mehrere
Backend-Prozesse bleiben außerhalb der unterstützten Betriebsweise.

## Vergleich als CSV

„Gefilterten Vergleich als CSV“ exportiert die gewählte Messgröße, Quelle,
Angriffsziel und gegebenenfalls den angehängten Bewertungssatz. Die Datei enthält
im langen Format Zeilen für Gruppen (`group`), gepaarte Vergleiche (`pair`) und
Fallprofile (`case`). Berechnungsgrundlage ist dieselbe Python-Zusammenfassung
wie in der Oberfläche. Modell und Mock-/LLM-Modus bleiben getrennt.

Zähler, Nenner, offene Urteile, nicht anwendbare Fälle und ausgeschlossene Paare
bleiben eigene Spalten. Nicht berechenbare Raten sind leer, nicht null Prozent.
Gepaarte Differenzen verwenden Prozentpunkte „links minus rechts“. Details zu
Ausschlüssen stehen als JSON in CSV-Zellen. Die Datei nutzt UTF-8 mit BOM und
standardkonforme CSV-Quotierung. Texte, die Tabellenprogramme als Formel
interpretieren könnten, erhalten ein führendes Apostroph; negative numerische
Differenzen bleiben Zahlen. Dies ändert nur den Export, nie Originalbelege.

## Gleichzeitige Bewertungsänderungen

Jedes Formular A/B liefert seine aktuelle Entwurfsrevision. Beim Speichern muss
diese Revision noch aktuell sein. Von zwei gleichzeitigen Schreibversuchen auf
denselben Stand wird nur einer veröffentlicht. Der andere erhält HTTP 409.

Die Oberfläche erhält dabei ihre ungespeicherten Eingaben. „Parallel gespeicherte
Bewertung“ zeigt den inzwischen gespeicherten Serverstand. Nach Prüfung kann
man den aktuellen Stand laden und die eigenen Eingaben bewusst verwerfen oder
die eigenen Eingaben ausdrücklich als neue Version speichern. Ein weiteres
zwischenzeitliches Speichern erzeugt erneut einen Konflikt. Alle bereits
veröffentlichten Entwurfsversionen bleiben erhalten. Zusammengeführte Urteile
bleiben schreibgeschützt; eine Konfliktbehandlung hebt diese Sperre nicht auf.

Dies verhindert versehentliche Überschreibungen. Es erzwingt keine unabhängigen
Bewertungen und bindet die wissenschaftlichen Slots nicht an GitHub-Konten.
Beide Autoren verwenden weiterhin bewusst getrennte Formulare und die
vereinbarte Bewertungsrubrik.

## Übergang zwischen Pages und Backend

`GET /api/health` weist `api_contract: 2` und die Fähigkeiten
`campaign_metadata_v1`, `review_revisions_v1`, `comparison_csv_v1` und
`workspace_backup_v1` aus. Die grundlegenden bestehenden Routen bleiben erhalten.

| Kombination | Verhalten |
|---|---|
| Neue Oberfläche, neues Backend | Namen/Tags, CSV und revisionsgeprüfte Bewertungen verfügbar. |
| Alte Oberfläche, neues Backend | Bestehende Leseabläufe bleiben möglich. Ein erster leerer Bewertungsstand kann gespeichert werden; ein weiteres Speichern ohne Revision wird mit verständlichem 409 abgewiesen. Oberfläche neu laden. |
| Neue Oberfläche, altes Backend | Bewertungsformulare ohne Revisionsfeld werden mit Erklärung schreibgeschützt. Zusätzliche Metadaten- und Downloadfunktionen zeigen den API-Fehler; auf Bereitstellung des Backends warten und neu laden. Unbenannte Mock-Starts behalten den bisherigen Request. |

Downloads sind authentifiziert wie andere Datenendpunkte. Eine neue Capability
aktiviert weder echte Modellaufrufe noch eine neue kostenpflichtige Ressource.
