# PR #30: Backup- und Archivpfade

Stand: 6. November 2026. Geprüfte Scannerrevision:
`6b48f567e708de55230029549fee7a27c06b3d93`. Grundlage sind die fünf
Sonar-Annotationen „Path Traversal via faulty LLM-supplied CLI arguments“ mit
den unten genannten IDs und die tatsächlichen Aufrufer im Repository.

**Ergebnis: fünfmal `not_actionable`, hohe statische Konfidenz.** Für die
jeweils behauptete Eingabeherkunft ist kein unterstützter Pfad vom Labormodell
zu CLI-Argumenten vorhanden. Die Einstufung gilt für diese konkreten Meldungen,
nicht als allgemeine Freistellung von Dateizugriffen oder Archivverarbeitung.
Es wurden keine Sonar-Zustände durch diese Prüfung verändert.

## Geprüfte Vertrauensgrenze

Die verbindlichen [Sicherheitsinvarianten](../../SECURITY.md) 1, 3, 5 und 8
verlangen beschränkte Modelltools, verwaltete Webpfade und sichere
Archivverarbeitung. Das [Bedrohungsmodell](../threat-model.md) grenzt den
Modellvorschlag vom ausdrücklich gestarteten Betreiber-CLI-Aufruf ab. Eine
zusätzliche scoped `SECURITY.md` existiert im geprüften Quellbaum nicht.

Diese Grenze ist im Code tatsächlich umgesetzt:

- `src/security_lab/core.py:33` definiert ausschließlich `read_ticket` und
  `append_note`. `_syntax_error` ab Zeile 88 lehnt andere Toolnamen und
  unerwartete Argumentfelder ab. Modellantworten, Artikel und PDF-Texte werden
  nicht zu Shellbefehlen oder `argparse`-Eingaben weitergereicht.
- `src/security_lab/backup.py::main` erhält `workspace`, `source`, `output`,
  `archive` und `destination` vom expliziten Prozessaufruf des Betreibers.
  Das Programm übernimmt keine vermeintlichen CLI-Anweisungen aus Beleginhalten.
- `src/security_lab/server.py::workspace_backup` besitzt **keinen Pfadparameter**.
  Der authentifizierte Handler verwendet den konfigurierten Workspace, den
  festen Repository-Quellpfad und `TemporaryDirectory` plus den festen Namen
  `security-lab-workspace.zip`. Es gibt keinen Web-Restore mit frei wählbarem Ziel.
- `src/security_lab/cli.py::_archive_campaign`, `_verify_archive` und
  `_restore_archive` erhalten ihre äußeren Pfade ebenfalls direkt aus den
  Betreiberargumenten. Der Nutzer darf ein Archiv außerhalb des Workspace
  speichern und in einen neuen externen Ordner wiederherstellen.

Ein separat eingesetzter Entwicklungsassistent mit bereits erteiltem
Betriebssystem-/Shellzugriff ist kein vom Labor ausgeführtes Modelltool. Die
Annotation enthält keinen zusätzlichen Wrapper, der einen solchen Zugriff als
Produktoberfläche bereitstellt. Das ist eine konkret geprüfte Herkunftsfrage,
keine Annahme, dass eine beliebige lokale Anwendung automatisch sicher sei.

## Einordnung je Meldung

Die Zeilennummern beziehen sich auf die oben festgehaltene Scannerrevision.

| Sonar-ID | Gemeldete Stelle | Datenfluss und Disposition | Positiver und negativer Gegenfall |
|---|---|---|---|
| `AaGwHoAa3f6_aqzNEjCM` | `src/security_lab/backup.py:466`, `destination.rmdir()` | `main → restore_workspace_backup →` Bereinigung der zuvor exklusiv angelegten Zielreservierung. Der Pfad kommt vom Betreiber; `rmdir` entfernt ausschließlich ein leeres Verzeichnis und bewahrt unerwartete konkurrierende Inhalte. `not_actionable`; kein aus Archiv oder Modell abgeleiteter Löschpfad. | Positiv: neues externes Restore-Ziel erhält `snapshot/`. Negativ: ein vor der Veröffentlichung konkurrierend angelegtes Ziel bleibt bestehen; es wird weder ersetzt noch rekursiv gelöscht. |
| `AaGwHoAa3f6_aqzNEjCL` | `src/security_lab/backup.py:374`, `os.link(candidate, output_path)` | Betreiberargument oder vom Webhandler erzeugter Temp-Pfad. Die Quelle ist ein selbst erzeugtes, vollständig geprüftes und synchronisiertes ZIP. Ausgabe innerhalb des Live-Workspace und vorhandene Ausgabedateien werden abgelehnt; der Hardlink überschreibt auch ein konkurrierend angelegtes Ziel nicht. `not_actionable`. | Positiv: ausdrücklich gewählte externe Sicherung. Negativ: interner Workspace-Ausgabepfad oder vorhandene Datei wird abgelehnt; Fehler hinterlassen kein veröffentlichtes Teilarchiv. |
| `AaGwHoAy3f6_aqzNEjCU` | `src/security_lab/archives.py:62`, `path.open("rb")` in `_sha()` | Interner, ausschließlich lesender Hashhelfer. Aufrufer übergeben den gewählten Archivpfad, Dateien eines zuvor inventarisierten Kampagnenbaums oder Dateien eines frisch extrahierten und pfadgeprüften Archivs. Backup-Quellpfade aus Metadaten durchlaufen zusätzlich `_safe_name` und eine begrenzte Commitkennung. Kein Modell-CLI-Dispatcher ruft den Helfer auf. `not_actionable`. | Positiv: Hash einer ausdrücklich ausgewählten externen ZIP und ihrer erhaltenen Kopie. Negativ: Archivmitglieder `../escape`, `/absolute`, `C:/escape`, Backslashpfade und Symlink-Einträge scheitern vor Extraktion/weiterer Belegprüfung. |
| `AaGwHoAa3f6_aqzNEjCN` | `src/security_lab/backup.py:460`, `destination.mkdir(exist_ok=False)` | Expliziter Betreiberpfad; `reject_symlinks(destination)` prüft zuvor Pfad und Eltern auf Symlinks/Junctions und lehnt `..`-Segmente ab. Die exklusive Reservierung verhindert das Ersetzen eines bereits existierenden Ziels. `not_actionable`; ein absoluter externer Zielpfad ist eine vorgesehene Restore-Funktion. | Positiv: neuer Zielordner außerhalb des ursprünglichen Workspace. Negativ: vorhandenes oder während der Prüfung hinzugekommenes Ziel verursacht `FileExistsError`. |
| `AaGwHoAa3f6_aqzNEjCK` | `src/security_lab/backup.py:463`, `temporary.rename(snapshot)` | Geprüfter Stagingbaum wird unter den festen Unterpfad `snapshot` der eben reservierten Betreiber-Zieldirectory verschoben. ZIP-Namen bestimmen weder die äußere Destination noch den Unterpfad. `not_actionable`. | Positiv: originale Dateien, Archivkopie und Restore-Quittung werden gemeinsam veröffentlicht. Negativ: manipuliertes ZIP/Inventar oder unsicherer Mitgliedspfad scheitert in `_verify_into`; es wird kein erfolgreicher Restore publiziert. |

Die Archivgrenze bleibt unabhängig davon erforderlich:
`src/security_lab/archives.py::_archive_members` verwendet `_safe_name` und
`_validate_archive_member`; absolute Pfade, `..`, Windows-Sonderpfade,
Kollisionen, Symlinks und Sonderdateien sind verboten. Erst danach schreibt
`_extract_verified_members` Hash-geprüfte Bytes mit exklusivem `xb` in einen
neuen temporären Baum. `src/security_lab/backup.py::_workspace_index` begrenzt
zusätzlich die erlaubten Archivpräfixe. Diese Kontrollen wurden beim Trace
mitbetrachtet; eine allgemeine Workspace-Pflicht für vertrauenswürdige äußere
CLI-Ziele würde die vorgesehene externe Sicherung verhindern.

## Vorhandene Verhaltensnachweise

Die statische Einstufung stützt sich auf die oben beschriebene Eingabeherkunft.
Folgende vorhandene Regressionen prüfen ergänzend die tatsächlichen Grenzen:

| Testdatei | Relevante Tests |
|---|---|
| `tests/test_workspace_backup.py` | `test_full_backup_roundtrip_keeps_unassigned_documents_reviews_and_code`, `test_cli_verify_restore_and_failure_exit_codes`, `test_rejects_changed_bytes_extra_members_schema_and_traversal`, `test_rejects_dirty_source_active_worker_unknown_files_and_internal_output`, `test_racing_destination_creation_is_not_overwritten`, `test_size_limit_and_atomic_publication_failure_leave_no_output` |
| `tests/test_archives.py` | `test_paths_links_duplicates_and_excessive_expansion_rejected`, `test_export_rejects_symlinks_and_inside_output`, `test_export_publishes_only_complete_synced_archive_without_overwriting_rival`, `test_hash_tamper_rejected_and_import_destination_not_created` |
| `tests/test_core.py` | `test_invalid_syntax_never_reaches_backend` enthält ausdrücklich `ToolCall("shell", ...)` und einen traversierenden `ticket_id`; `test_full_tool_schema_constant_and_same_prompt` prüft die gemeinsame Tooloberfläche. |

Separat wurde die nicht sicherheitsbezogene Meldung `AaGwHoAa3f6_aqzNEjCJ`
behoben: das wiederholte Archivpräfix `source/` verwendet jetzt die Konstante
`SOURCE_PREFIX`. Diese Änderung verschiebt keine Vertrauensgrenze.
Nach dieser Konstantenänderung am 6. November unter Linux ausgeführt:
19 Backup-Tests, 25 Archivtests und 17 Kern-Tests bestanden; Ruff für
`backup.py` ebenfalls erfolgreich. Das sind Regressionstests, keine Behauptung
einer vollständigen dynamischen Sicherheitsprüfung.

Grenze der Einordnung: Die importierten Annotationen liefern Titel, Ort und ID,
keinen vollständigen zusätzlichen Exploit-Trace. Die Prüfung erfasst die
aufgeführten ausgelieferten Aufrufer und ihre Eingaben; sie behauptet keinen
allgemeinen Schutz vor einem bereits kompromittierten Betriebssystemkonto oder
einer künftig zusätzlich eingerichteten Shell-/CLI-Modellintegration.
