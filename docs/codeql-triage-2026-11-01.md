# Einzelprüfung der 23 CodeQL-Meldungen

Geprüfter Ausgangsstand: `2e44a3a866e9955e9f6281a42c148a1c5326da45`,
1. November 2026. Die Zeilenangaben beziehen sich auf diesen Commit.
GitHub zeigte zunächst 23 offene Meldungen mit Schweregrad High: #1–#22 zur
Regel `py/path-injection` und #23 zur TLS-Versionskonfiguration der Test-Fixture.
Die Detailseite und bei Pfadinjektionen der vollständige über „Show paths“
sichtbare Datenfluss wurden für **jede ID** geprüft.

**Disposition am 1. November 2026:** #1–#22 wurden einzeln auf GitHub als
False positive geschlossen. Jede Schließung enthält die konkrete Begründung zu
Quelle, Validator und Senke; die folgenden Tabellen halten diese Bewertung fest.
#23 bleibt bis zum Merge der expliziten TLS-Mindestversion und einer erneuten
CodeQL-Analyse offen. Es wurde keine Scannerregel deaktiviert und keine globale
Pfadausnahme ergänzt. Die geprüften Pfadvalidatoren bleiben unverändert.

## Gemeinsame Quelle und geprüfte Grenze

Die Pfade der Meldungen #1–#15 beginnen bei `document_id` in `server.py:434`, dem
HTTP-Endpunkt `POST /api/documents/{document_id}/confirm`, und werden in Zeile 436
an `confirm_document` übergeben. Der Pfad ist tatsächlich zunächst nutzerkontrolliert.
Die Begrenzung wird jedoch vor jeder gemeldeten Dateioperation wirksam:

- `documents.py:28,57–60`: `_managed` verlangt `DOCUMENT_ID.fullmatch(document_id)`
  mit `doc-[0-9a-f]{32}\Z`. Dadurch sind nur ein ASCII-Verzeichnisname mit fester
  Länge, weder Separatoren, Punktsegmente, Laufwerke, UNC-Pfade, Datenstreams noch
  ein angehängter Zeilenumbruch zulässig.
- Der Speicherstamm stammt aus `CampaignJobs.documents` bzw. dem konfigurierten
  Workspace, nicht aus dem HTTP-Parameter. `_managed` ruft `reject_symlinks` mit
  diesem Stamm auf. Das prüft die Zugehörigkeit sowie Symlinks und unter Python
  3.12 verfügbare Windows-Junctions für das Verzeichnis und alle Elternteile.
- `load_document` prüft zusätzlich die vier festen Dateinamen (`document.json`,
  `original.pdf`, `extracted.txt`, `confirmation.json`) auf Links, bevor deren
  Metadaten/Inhalte gelesen werden. Größenbegrenzungen und Original-/Texthashes
  werden anschließend validiert.
- Schreiben einer Bestätigung setzt erfolgreiches Laden und den konkreten,
  übereinstimmenden Texthash voraus. Der Zielname ist konstant. Veröffentlichung
  erfolgt atomar und ohne Überschreiben durch `write_json_new`.

Der sichtbare CodeQL-Pfad läuft durch `_managed` und `reject_symlinks`, behandelt
deren Rückgabe aber weiterhin als unbereinigt. Der kompilierte Regex-Validator
wird hier offenbar nicht als ausreichende Schranke modelliert. Diese Aussage ist
eine Schlussfolgerung aus dem angezeigten Datenfluss und dem geprüften Code;
der Scanner selbst wurde nicht lokal erneut ausgeführt.

## Disposition je Meldung

| ID | Gemeldete Senke | Sichtbarer Datenfluss nach `server.confirm` | Einzelbewertung |
|---|---|---|---|
| #1 | `batch.py:76`, `path.parent.mkdir` | `confirm_document:220` → `_managed` → `reject_symlinks` → `write_json_new:65,75,76` (16 Schritte) | False positive für Pfadinjektion: Elternverzeichnis liegt unter festem Speicherstamm und bereits validierter Dokumentkennung. |
| #2 | `batch.py:80`, `temporary.open("xb")` | Gleicher Ursprung, zusätzlich temporärer Name aus `path.name` und serverseitigem Zufallswert (17 Schritte) | False positive: ausschließlich `confirmation.json.<random>.tmp` im validierten Verzeichnis; exklusives Anlegen. |
| #3 | `batch.py:85`, Quellargument `temporary` von `os.link` | Gleicher Ursprung über temporären Namen (17 Schritte) | False positive: Linkquelle ist die vorher exklusiv angelegte vollständige temporäre Datei. |
| #4 | `batch.py:85`, Zielargument `path` von `os.link` | Gleicher Ursprung über festen Bestätigungspfad (16 Schritte) | False positive: Ziel ist ausschließlich `confirmation.json` unter validierter Kennung; ein vorhandenes Ziel wird nicht ersetzt. |
| #5 | `batch.py:88`, `temporary.unlink` | Gleicher Ursprung über temporären Namen (17 Schritte) | False positive: bereinigt nur die in diesem Aufruf selbst angelegte temporäre Datei (`created`-Schutz). |
| #6 | `documents.py:163`, `stat(document.json)` | `confirm_document:217` → `load_document:158,159` → `_managed` → `reject_symlinks` → feste Datei (15 Schritte) | False positive: feste Metadatendatei; gültige Kennung und Linkprüfung gehen dem Stat voraus. |
| #7 | `documents.py:163`, `stat(original.pdf)` | Derselbe validierte Ladepfad (15 Schritte) | False positive: fester Originaldateiname; gültige Kennung und Linkprüfung gehen dem Stat voraus. |
| #8 | `documents.py:163`, `stat(extracted.txt)` | Derselbe validierte Ladepfad (15 Schritte) | False positive: fester Extraktionsdateiname; gültige Kennung und Linkprüfung gehen dem Stat voraus. |
| #9 | `documents.py:165`, `read_text(document.json)` | Derselbe validierte Ladepfad (15 Schritte) | False positive: kein Dateiname aus Metadaten oder Anfrage wird geöffnet; fester Name und Größen-/Linkprüfung. |
| #10 | `documents.py:170`, `read_bytes(original.pdf)` | Derselbe validierte Ladepfad (15 Schritte) | False positive: festes Original, zuvor auf Link und Größe geprüft; anschließend Hashprüfung. |
| #11 | `documents.py:171`, `read_bytes(extracted.txt)` | Derselbe validierte Ladepfad (15 Schritte) | False positive: feste Extraktion, zuvor auf Link und Größe geprüft; anschließend Hashprüfung. |
| #12 | `documents.py:186`, `exists(confirmation.json)` | Derselbe validierte Ladepfad (15 Schritte) | False positive: fester Bestätigungsname; auch dieser Dateipfad wird bereits in der Schleife vor dem Lesen auf Links geprüft. |
| #13 | `documents.py:187`, `stat(confirmation.json)` | Derselbe validierte Ladepfad (15 Schritte) | False positive: fester Name, vorgelagerte Linkprüfung; begrenzt Bestätigungsgröße auf 2048 Bytes. |
| #14 | `documents.py:189`, `read_text(confirmation.json)` | Derselbe validierte Ladepfad (15 Schritte) | False positive: fester Name; Größen-/Linkprüfung davor und Zuordnung zum Texthash danach. |
| #15 | `documents.py:221`, `path.exists` | `confirm_document:220` → `_managed` → `reject_symlinks` → fester Bestätigungspfad (13 Schritte) | False positive: wiederholt streng validierte Kennung; `load_document` einschließlich Prüfung der Bestätigungsdatei bereits erfolgreich. |

Die jeweilige nachvollziehbare Detailseite lautet
`https://github.com/sxba-04/llm-agent-security-lab/security/code-scanning/<ID>`.
#6–#8 wurden zusätzlich anhand der hervorgehobenen Teiloperation in derselben
Quellzeile unterschieden. #3 und #4 betreffen getrennt Linkquelle und Linkziel.

## Ausgeführte Verifikation

Die Prüfungen liefen auf dem oben genannten Ausgangsstand mit den zusätzlichen
Regressionstests. `uv sync --locked --extra web --group dev` war erfolgreich.
Es gab keine Modell-API-Aufrufe oder Netzwerktests gegen das produktive Backend.

Neue Datei `tests/test_document_path_boundaries.py`: vier bestandene Tests unter
Linux/Python 3.12.14. Sie prüfen reales Verhalten statt einer Nachbildung des
Regex-Ausdrucks:

1. 16 manipulierte Identitäten einschließlich POSIX-/Windows-Traversal,
   absolutem Pfad, UNC, Alternate Data Stream, Unicode, falscher Länge,
   Nullbyte/Zeilenumbruch: Laden und Bestätigen scheitern; externe gültige
   Dokumentbelege bleiben bytegleich und es wird kein Speicherordner angelegt.
2. Jeder der vier festen Dateinamen wird einzeln durch einen tatsächlichen
   Symlink auf eine externe Datei ersetzt: Laden/Bestätigen scheitern, externe
   Bytes bleiben unverändert, keine temporäre Bestätigung bleibt zurück.
3. Tatsächlicher Verzeichnislink mit syntaktisch gültiger Kennung auf externes
   gültiges Dokument: keine Bestätigung außerhalb des Speichers.
4. Tatsächlicher FastAPI-Testclient, Upload und sechs URL-kodierte schädliche
   Parameter: HTTP 400/404, Belege bleiben unverändert; reguläre Bestätigung
   desselben gültigen Dokuments danach HTTP 200.

Bestehende Dokumenttests ebenfalls erfolgreich (7 Tests), einschließlich
Fehlerbehandlung bei `fsync` und nachfolgend erfolgreichem Retry.
Die bestehenden Tests atomarer Schreibvorgänge liefen ebenfalls erfolgreich:
9 Tests, davon 8 bestanden und der echte Windows-Dateifreigabetest unter Linux
erwartungsgemäß übersprungen. Sie prüfen unter anderem konkurrierende
Create-if-absent-Schreiber und fehlgeschlagene Veröffentlichung.

Die Tests führen echte Symlinks unter Linux aus. Unter Windows werden diese
gezielt übersprungen, wenn das Betriebssystem deren Erstellung nicht gestattet;
das ist kein Nachweis echter Windows-Junction-Tests. Die tatsächliche Windows-CI
steht für diesen zusätzlichen Teststand noch aus.

## Grenzen der Pfadprüfung

Es wurde kein per HTTP erreichbarer Pfadinjektionsfehler der Meldungen #1–#15
bestätigt. Ihre False-positive-Disposition erfolgte einzeln mit Verweis auf
Validator, Senke und Tests. Globale Ausschlüsse oder Unterdrückungskommentare
wurden dafür nicht eingeführt.

Dateisystemprüfungen bieten keine vollständige TOCTOU-Isolation gegen jemanden,
der zwischen Prüfung und Zugriff bereits beliebige Verzeichnisse des selben
Betriebssystemkontos austauschen kann. Dies ist keine durch den HTTP-Parameter
gewonnene Fähigkeit. Der Dienst bietet auch bewusst keine Trennung zwischen
den vertrauenswürdigen Betreibern desselben Workspace. Diese Grenzen werden
nicht als behoben oder durch die Tests widerlegt dargestellt.

## Ergänzende Einzelprüfung #16–#23

Auch diese Meldungen wurden einzeln auf GitHub einschließlich aller dort
angezeigten Datenflüsse geprüft. Der Prüfstand ist derselbe oben genannte Commit.

| ID | Gemeldete Senke | Wirksame Grenze und Bewertung |
|---|---|---|
| #16 | `jobs.py:36`, Worker-Lock öffnen | GET-Kampagne und POST-Abbruch führen über die registrierte Kampagne und `_owner`. Dessen `NEW_ID.fullmatch` akzeptiert nur `campaign-` plus 32 Hexzeichen; ohne gültigen Eigentümereintrag endet die Wiederherstellung vor dem Lock. Zusätzliche Linkprüfung. False positive für Pfadinjektion. |
| #17 | `jobs.py:38`, Worker-Lock stat | Beide Datenflüsse wie #16; Stat erfolgt erst nach dem geschützten Öffnen. Quelle und eigene Senke geprüft. False positive. |
| #18 | `jobs.py:132`, Eigentümerdatei exists | Derselbe GET-/Abbruch-Ursprung. Vor `workers/<id>.json` greifen exakter ID-Validator und `reject_symlinks(path, workspace)`. False positive. |
| #19 | `jobs.py:134`, Eigentümerdatei lesen | Beide Datenflüsse wie #18; Lesen erst nach ID-, Speichergrenzen-, Link- und Existenzprüfung. False positive. |
| #20 | `server.py:560`, Frontend-Kandidat is_file | Die Route verwirft Traversal und Backslashes; `reject_symlinks(candidate, frontend)` verwirft absolute Pfade außerhalb des Builds sowie Links/Junctions vor Stat. False positive. |
| #21 | `server.py:562`, zweites is_file | Der Kandidat ist entweder die bereits geprüfte Datei oder das konstante, erneut geprüfte `frontend/index.html`. Der SPA-Fallback führt keinen ungeprüften Pfad ein. False positive. |
| #22 | `server.py:564`, FileResponse | Nur der auf Build-Grenzen und Dateityp geprüfte Kandidat wird ausgeliefert. HTTP-Angriffstests lesen keinen externen Sentinel; reguläre Assets bleiben verfügbar. False positive. |
| #23 | `frontend/e2e-hosted/server.py:76`, TLS-Socket | Python ≥3.12 ist vorgeschrieben. `SSLContext(PROTOCOL_TLS_SERVER)` setzt bereits seit Python 3.10 mindestens TLS 1.2. Der Wert wird zusätzlich explizit gesetzt; dies ist Härtung, keine Reparatur einer nachgewiesenen TLS-1.0-Freigabe. Meldung noch offen; Merge und erneute CodeQL-Analyse stehen aus. |

Die neuen Jobs-Tests prüfen manipulierte Kampagnenkennungen über Manifest und
Abbruch, ohne Workerdateien oder ursprüngliche Belege zu verändern. Die
Frontend-Tests prüfen Traversal, kodierte absolute Pfade, Backslashes und nach
dem Serverstart eingefügte Symlinks sowie funktionierende Assets und SPA-Routen.
Symlink-Tests melden ausdrücklich einen Skip, wenn das Betriebssystem keine
Testlinks zulässt.

Die tatsächliche TLS-Fixture wurde vor und nach der Ergänzung mit synthetischen
MemoryBIO-Handshakes unter Python 3.12.14 / OpenSSL 3.5.8 geprüft: TLS 1.0 und
1.1 wurden serverseitig mit `UNSUPPORTED_PROTOCOL` abgewiesen; TLS 1.2 und 1.3
funktionierten mit Zertifikats- und Hostnamenprüfung. Es wurde kein externer
Testport geöffnet und keine Zertifikatsprüfung deaktiviert.

Referenz: [Python 3.12 SSLContext](https://docs.python.org/3.12/library/ssl.html#ssl.SSLContext), Änderung ab Version 3.10.

## Ergänzende Belegprüfung

Die zusätzliche Exportprüfung bestätigte einen separaten echten Fehler: Ein
fehlgeschlagener finaler Kopiervorgang konnte eine unvollständige ZIP hinterlassen
und den erneuten Export blockieren. Die Veröffentlichung erfolgt jetzt erst nach
Prüfung und Dateisynchronisierung atomar ohne Überschreiben. Eine unabhängige
Prozessabbruchprüfung unmittelbar davor und danach bestätigte: entweder keine
endgültige Datei oder ein vollständig verifizierbares Archiv. Originalbelege
blieben unverändert. Das ist kein Nachweis von Verzeichnisdurabilität bei
Stromausfall und keine neue Speicherzusage für Render.

Als dauerhafte Sicherungsform wählte das Team lokale, versionierte ZIP-Downloads
mit Archivprüfung und probeweiser Wiederherstellung. Die technische Prüfung
verwendete synthetische Mock-Belege. Ein tatsächlicher Download und die
Wiederherstellung vorhandener Nutzerkampagnen aus dem gehosteten Dienst wurden
ohne den dort erforderlichen Zugangscode nicht ausgeführt. Ein automatischer
Serverexport oder Cloud-Backupdienst wurde nicht eingerichtet.

Gesamter lokaler Stand mit Exportkorrektur, TLS-Mindestversion und zehn neuen
Regressionstests: `uv run --locked --extra web python -m unittest discover -s tests -v`
führte unter Linux 281 Tests aus; 280 bestanden, der echte Windows-Dateifreigabetest
wurde erwartungsgemäß übersprungen. Windows- und Browser-CI für diesen zusätzlichen
Stand stehen noch aus und müssen vor dem Merge am aktuellen PR-Commit erfolgreich
abgeschlossen sein. Die unabhängige Code- und Sicherheitsprüfung des
Implementierungspatches fand keine blockierenden Befunde. Die Änderungen betreffen
weder das Versuchsdesign noch die B/F/P/FP-Bedingungen; Mock-Prüfungen sind keine
empirischen Modellbefunde.
