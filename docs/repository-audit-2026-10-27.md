# Repository-Prüfung und Verbesserungsplan vom 27. Oktober 2026

Ausgangspunkt ist PR #3 mit der auf dem LUBW-Laptop reproduzierten Windows-Dateisperre. Ziel dieser Runde ist ein verlässlicher Mock-Prüfstand; die Modellanbindung und echte Modellversuche werden nicht aktiviert. Die Prüfung umfasst Ausführung und Grenzen, Auswertung, Quellen/PDFs, Bewertungen und Archive, Oberfläche, Windows-Betrieb sowie Review-Regeln. Parallele Quellcodeprüfungen und eine unabhängige technische Gegenprüfung ergänzen gezielte Regressionstests. Dies ist keine Garantie vollständiger Fehlerfreiheit und kein behaupteter registrierter Repository-Vollscan des Codex-Security-Dienstes.

## Vor der Umsetzung festgelegte Reihenfolge

1. PR #3 unabhängig nachvollziehen, beide Codex-Reviews und Copilot erneut anfordern, aktuelle CI prüfen und den PR abschließen.
2. Host-/HTTP-/PDF-Grenzen, Fehlerbehandlung und Belegintegrität prüfen.
3. Szenarien, Offenlegungsmetriken, Paarbildung und Bewertungsablauf gegen die dokumentierte Methode prüfen.
4. Plattformvoraussetzungen, CI, `AGENTS.md`, `SECURITY.md` und Review-Einstellungen präzisieren.
5. Bestätigte Fehler mit Regressionen korrigieren und den Gesamtstand als separaten Folge-PR prüfen lassen.

## Bestätigte Befunde und Korrekturen

| Bereich | Befund | Änderung und Nachweis |
|---|---|---|
| Windows-Speicherung (PR #3) | Kurzzeitiges gleichzeitiges Lesen konnte den Austausch von `manifest.json` verhindern. | Begrenzte Wiederholung nur der Veröffentlichung einer bereits geschriebenen Datei; keine Wiederholung von Modell-/Toolarbeit. Windows-Handle-Test und portable Fehlerfälle. |
| Neue unveränderliche JSON-Dateien | Ein abgebrochener Schreibvorgang konnte einen unvollständigen Bewertungsstand hinterlassen und spätere Versuche blockieren. | Vollständig synchronisierte Tempdatei atomar und ohne Überschreiben veröffentlichen; Schreib-, Sync-, Veröffentlichungs- und Konkurrenzfehler testen. |
| PDF-Quellen | Eine beschädigte Quelle konnte das gesamte Quellenverzeichnis unbenutzbar machen. Eine Bestätigung durfte nicht auf einen inzwischen anderen ausgewählten Text übergehen. | Beschädigte Einträge getrennt anzeigen und von Auswahl/Bestätigung ausschließen; Bestätigung an Dokument-ID und Texthash binden. Backend- und React-Regressionen. |
| Bewertung und Navigation | Ein Seitenwechsel konnte ungespeicherte Bewertungen oder Klärungen verlieren. | Bestätigung bei internen Links, Slotwechsel und Browserhistorie; Schutz beim Schließen/Neuladen. Mehrstufige Historienwechsel gezielt prüfen. |
| Wiederhergestellte Bewertungen | Ursprüngliche Kampagnenkennungen passten nach einem Restore nicht mehr zur aktuellen Discovery-Kennung; Kopien konnten kollidieren. | Aktuelle API-Zuordnung getrennt von unveränderlicher Archivherkunft behandeln; Original plus Kopie und frischen Workspace prüfen. |
| Sichtbare Offenlegung | Ein Canary in einer neu gespeicherten lesbaren Ticketnotiz fehlte in der Offenlegungsmetrik. | Neue Notizen zusätzlich zur Antwort prüfen und Fundstellen ausweisen; unveränderte und nicht lesbare Notizen ausschließen. |
| Gepaarte Vergleiche | Unterschiedliche Laufgrenzen oder Schutzversionen konnten unbemerkt gepaart werden. | Aufgezeichnete Grenzen und konsistente Versionsnachweise verlangen; fehlende, widersprüchliche oder unterschiedliche Nachweise explizit ausschließen. Alte Einzelprofile bleiben lesbar. |
| Plattform und CI | Der Frontend-Mindeststand war nicht maschinenprüfbar; echte Browserprüfungen liefen nur auf Linux. | Node 24 ab 24.15.0 im Paketvertrag erzwingen; Python und Browser jeweils auf Windows/Linux; doppelte Feature-Branch-Workflows vermeiden. |
| Review-Kontext | Experimentell absichtliches Verhalten und nicht tolerierbare Infrastrukturfehler mussten präziser getrennt werden. | Konkrete Code-Review-Regeln, Sicherheitsinvarianten und ein Bedrohungsmodell; bekannte Grenzen sind keine pauschalen Ausschlüsse. |

## Entscheidungen und Grenzen

FastAPI/React, Python, JSON als Fallformat und PDF als vorbereiteter Artikelimport bleiben gesetzt. Mock-Kampagnen prüfen das Instrument; sie liefern keine empirischen Aussagen zu LLM-Sicherheit. B/F behalten den beabsichtigten ungeschützten synthetischen Backendzugriff. P/FP und die äußeren Infrastrukturgrenzen dürfen dadurch nicht abgeschwächt werden.

Bewertungs- und Quelldateien werden nicht stillschweigend repariert oder überschrieben. Hashes sind Integritätsnachweise, keine Signaturen. Für atomare neue Dateien benötigt das Arbeitsverzeichnis Hardlink-Unterstützung (beispielsweise lokales NTFS); ungeeignete Dateisysteme führen zu einem Fehler statt einer unsicheren Ersatzoperation.

PR #3 wurde nach erfolgreichen Codex-Code- und Security-Reviews auf `186ca6d` und bestandener CI als `9a0dfebc` gemergt. Copilot blieb wegen seines eigenen Kontingents nicht verfügbar; dafür liegt die ausdrückliche Ausnahme des Nutzers vor. Für den Folge-PR sind Ergebnisse am endgültigen Commit maßgeblich. Konkrete Testergebnisse stehen in [validation.md](validation.md), Review-Empfehlungen in [review-settings.md](review-settings.md).

## Bewusst noch offene Arbeit

- Beide Autoren prüfen die repräsentativen Szenarien, Artikel/PDF-Extraktionen und Bewertungsrubrik fachlich und dokumentieren ihre eigenen Beiträge.
- Jonahs und die privaten Rechner benötigen ihren eigenen dokumentierten Funktionstest; derselbe Account synchronisiert keine lokalen Kampagnendaten.
- Vor dem API-Pilot: äußere Isolation praktisch einrichten und prüfen, Modell-/Preisauswahl dokumentieren und Parameter-/Tokenlimit-Provenienz bis in den Einzellauf vervollständigen. Budgetreservierungen und tatsächliche Kosten getrennt ausweisen.
- Erst nach Pilot und Freigabe den getrennten Haupttestkatalog erstellen und einfrieren, echte Modellläufe durchführen und unabhängig menschlich bewerten.

Diese offenen Punkte werden nicht durch erfundene Bewertungen, ein automatisch gesetztes Freigabefeld oder einen vorzeitig gestarteten kostenpflichtigen Versuch ersetzt.
