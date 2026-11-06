# Gesamtsicherung und getrennte Wiederherstellung

Die Werkbank kann den gesamten verwalteten Forschungsbestand als ZIP sichern.
Einzelne Kampagnenarchive bleiben nützlich, enthalten aber beispielsweise noch
keinem Versuch zugeordnete PDF-Originale nicht. Die Gesamtsicherung verändert
keine Bewertungen und führt keine Modellaufrufe aus.

## Umfang und Grenzen

| Bestandteil | Verhalten |
|---|---|
| Kampagnen, Originalereignisse, Fall-Snapshots | Originalbytes einschließlich abgebrochener, bereits geschlossener Kampagnen |
| PDF-Bestand | Auch unzugeordnete und noch nicht bestätigte Originale, Extraktion und Metadaten; vorhandene Bestätigung bleibt erhalten |
| Bewertungen | Original-CSV, Entwürfe, Versionen und Klärungen; auch ältere Bewertungssätze im Workspace-Hauptverzeichnis |
| Kampagnennamen, Tags und Studienmanifest | Kanonische Dateien werden mitgesichert |
| Dokumentierter Betriebsnachweis | Ausschließlich `operations/persistence-20261102/`: alle begrenzten regulären Originaldateien werden bytegleich mitgesichert; gesonderter Nachweis, keine wissenschaftliche Kampagne |
| Code und Lockdateien | Unveränderliche Git-Snapshots des aktuellen Commits und der verfügbaren, in Kampagnen vermerkten älteren Commits; keine Installation oder Ausführung beim Prüfen |
| Downloadcache und Betriebssperren | `exports/` und `workers/*.lock` sind ausdrücklich ausgeschlossen; sie sind keine Forschungsbelege |
| Secrets und Sitzungen | Keine Konfiguration aus Umgebungsvariablen, Git-Zugangsdaten oder OAuth-/Laborsitzungen; unbekannte Workspace-Einträge führen zum Abbruch statt zur stillen Aufnahme |

Ein älterer Commit kann beispielsweise in einem flachen Hosting-Klon fehlen.
Die Belege werden trotzdem gesichert, der Bericht nennt dann
`missing_commits` und `source_evidence_complete: false`. Auch bei abweichenden
aufgezeichneten Quellcode-Prüfsummen bleibt diese Angabe falsch. Das fehlende
Original muss aus dem ursprünglichen Repository/Arbeitsstand ergänzt werden;
ein neuer Code-Snapshot ersetzt es nicht. Änderungen an bereits versionierten
Dateien im aktuellen Checkout müssen vor einer Sicherung committed oder
zurückgenommen werden. Unversionierte lokale Dateien gehören nicht zum
unveränderlichen Git-Code-Snapshot.

Die Grenzen entsprechen dem bestehenden Archivformat: höchstens 10.000 Dateien,
64 MiB je Datei, 512 MiB entpackte Daten und 512 MiB ZIP. Maximal 32 verschiedene
Code-Commits werden in einem Backup berücksichtigt. Die Sicherung braucht freien
Platz für temporäre Prüfung und ZIP; sie ist kein Speichererweiterungsmechanismus.

Der historische [Persistenznachweis vom 2. November](validation.md) liegt bewusst
außerhalb der UI-Kampagnenablage. Seine verschachtelten technischen Mock-Läufe,
der unbestätigte PDF-Import, das Kampagnen-ZIP und der damalige Prüfplan werden
erhalten, aber bei diesem Backup nicht erneut semantisch als Forschungsbelege
validiert. `supplementary_operations` nennt die Dateien und ihren Umfang sowie
`verification: backup_inventory_and_sha256_only` und
`semantic_evidence_verified: false`. Diese Dateien fließen nicht in die
Kampagnen-, PDF-, Bewertungs- oder Codevollständigkeitsangaben der regulären
Forschungsbelege ein. Eine erfolgreiche Gesamtsicherung ersetzt daher keine
erneute Betriebsprüfung. Weitere Unterverzeichnisse in `operations/` werden
bis zu einer ausdrücklich geprüften Erweiterung abgelehnt; Links, Sonderdateien
und die bestehenden Größenbegrenzungen bleiben auch hier verboten.

## Sicherung aus der laufenden Werkbank

1. Mock-Kampagne beenden und PDF-Import abschließen lassen.
2. Unter **Versuche → Gesamten Forschungsbestand sichern** die ZIP herunterladen.
3. Die Datei außerhalb des Render-Dienstes aufbewahren und wie unten prüfen.
4. Vor echten Pilotaufrufen und wichtigen Bereitstellungen zusätzlich in ein
   neues Verzeichnis wiederherstellen und die erhaltenen Quellen/Bewertungen
   öffnen. Eine gültige Prüfsumme allein ist noch keine Wiederherstellungsübung.

Der authentifizierte Endpunkt `GET /api/workspace/backup` sperrt für die
Snapshot-Erstellung die bestehenden Bewertungs-, Start- und PDF-Schreibpfade.
Aktive Kampagnen und laufende Extraktionen werden abgelehnt. Der bestehende
Betrieb mit einem Prozess/einer Instanz ist Voraussetzung. Ein unabhängig
parallel gestarteter CLI-Schreiber ist nicht durch diese HTTP-Sperre geschützt;
solche Zugriffe sind während einer Sicherung zu unterlassen. Zusätzlich erkennt
der Export geänderte Datei-Inventare und Bytes und veröffentlicht nur einen
vollständig geprüften Snapshot.

Es wurde kein zusätzliches Cloudkonto, kostenpflichtiger Speicher und kein
periodischer externer Sicherungsjob eingerichtet. Eine ZIP im temporären
Downloadordner des Dienstes ist keine externe Sicherung. Sebastian und Jonah
müssen für die eigentlichen Studienbelege einen zugänglichen externen Ablageort
mit Aufbewahrung und Verantwortlichkeit festlegen. Bis dahin eignet sich der
explizite Download vor jeder relevanten Änderung als manueller Ablauf; der
Erfolg wird über Prüfung und Wiederherstellungsprotokoll belegt.

## Lokaler Wartungsablauf

PowerShell-Beispiel aus einem sauberen Repository-Klon mit dem regulären lokalen
Workspace `runs/`; bei einem abweichenden Startparameter auch hier den tatsächlich
verwendeten Workspace einsetzen. `D:\Studienbelege` ist ein vom Betreiber gewählter
Ablageort außerhalb des Workspace. Zuerst alle
Programme stoppen, die denselben Workspace verändern. Die Bestätigungsoption
`--writers-stopped` stoppt selbst keine Prozesse.

```powershell
uv run --locked --extra web python -m security_lab.backup export --workspace runs --source . --output D:\Studienbelege\gesamt-2026-11-06.zip --writers-stopped
uv run --locked --extra web python -m security_lab.backup verify D:\Studienbelege\gesamt-2026-11-06.zip
uv run --locked --extra web python -m security_lab.backup restore D:\Studienbelege\gesamt-2026-11-06.zip D:\Studienbelege\wiederherstellung-2026-11-06
```

Der Zielordner für `restore` darf **noch nicht existieren**. Die Wiederherstellung
reserviert ihn exklusiv und legt darin einen atomar veröffentlichten Unterordner
`snapshot/` an. Dieser enthält:

- `workspace/`: separat prüfbarer Forschungsbestand für einen lokalen Teststart;
- `source/<commit>/`: eingefrorene, geprüfte Quelldateien und Lockdateien;
- `original-backup.zip`: bytegleiche ursprüngliche Sicherung;
- `restore-receipt.json`: Zeit, Archivhash, Umfang und Prüfergebnis.

Die Wiederherstellung schreibt nicht in den produktiven Workspace. Sie führt
den enthaltenen Code nicht aus und startet keine Experimente. Erst nach eigener
Prüfung kann ein vertrauter lokaler Launcher auf den wiederhergestellten
`snapshot/workspace/` zeigen. Der JSON-Bericht gibt den vollständigen
Workspace-Pfad aus. Alte Sitzungen werden damit nicht wiederhergestellt.

## Prüfbericht richtig lesen

| Feld | Aussage |
|---|---|
| `verified` | ZIP-Inventar und Prüfsummen, Kampagnen-/PDF-/Bewertungsbezüge wurden geprüft |
| `authenticity_verified` | Bleibt `false`: Wer Bytes und Index gemeinsam ersetzen kann, kann eigene konsistente Belege herstellen |
| `evidence_complete` | Alle laut Laufmanifest benötigten Ereignisdateien sind vollständig; entspricht der bisherigen Kampagnenprüfung |
| `campaigns_complete` | Alle enthaltenen Kampagnen haben alle geplanten Läufe abgeschlossen; ein zulässig abgebrochener Versuch bleibt hier unvollständig |
| `source_evidence_complete` | Alle aufgezeichneten Code-Prüfsummen der Kampagnen passen zu mitgesicherten Git-Snapshots |
| `campaign_source_verified` | Zeigt fehlende/abweichende Originalstände je Kampagne |
| `supplementary_operations` | Getrennt aufgeführte historische Betriebsdateien; nur ZIP-Inventar und Byte-Prüfsummen geprüft, keine erneute semantische Freigabe |
| `engineering_only` | Ausschließlich Mock-Belege; kein empirischer Nachweis realer Modelle |

Abbruch oder fehlender historischer Code sind deshalb nicht automatisch ein
Integritätsfehler. Beschädigte Belege werden dagegen mit einer Fehlermeldung
abgelehnt und bleiben am Ursprungsort unverändert. Nicht durch Löschen oder
Umetikettieren „reparieren“; die Ursache zuerst anhand der Originale klären.

## Technischer Nachweis und reale Abnahme

`tests/test_workspace_backup.py` prüft mit synthetischen Daten unter anderem:
Gesamtexport/Restore einschließlich unzugeordneter PDFs und Bewertungen,
verfügbare und fehlende historische Quellstände, abgebrochene Versuche,
Manipulation auch mit neu berechnetem ZIP-Index, Pfadtraversierung, unbekannte
Schemaversionen, aktive Worker, konkurrierende Änderungen, Größenlimits und
fehlgeschlagene atomare Veröffentlichung. Der Test führt die CLI-Befehle
`export`, `verify` und `restore` ebenfalls aus. Die HTTP-Sperren werden separat
in den API-Tests geprüft. Ausgeführt am 6. November 2026 auf Linux; ein echter
Windows-Arbeitsplatz und eine produktive Wiederherstellungsübung benötigen einen
eigenen Nachweis.

Für eine reale Übung Datum, Quell-Commit, Archiv-SHA256, externen Ablageort,
Anzahl Kampagnen/PDFs/Bewertungsversionen, Zielordner sowie tatsächlich geprüfte
Ansichten festhalten. Automatische Fixture-Tests ersetzen weder menschliche
Bewertungen noch Freigaben von PDF-Texten. Dieses Paket wurde mit Codex erstellt;
es verändert das Versuchsmodell B/F/P/FP nicht.
