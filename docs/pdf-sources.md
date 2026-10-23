# PDF-Wissensartikel

Die Konzeptunterlagen legen den Text eines fest ausgewählten Wissensartikels als Angriffsfläche fest. Sie schreiben kein Dateiformat vor. Am 23. Oktober 2026 hat das Team zusätzlich den PDF-Import beschlossen. Die Tickets bleiben strukturierte synthetische Datensätze; die PDF liefert den Artikeltext.

## Kontrollierter Import

1. Eine synthetische textbasierte PDF hochladen. Für den Einstieg lassen sich die Artikelfassungen der Entwicklungsfälle als Beispiel-PDF herunterladen.
2. Die Vorschau des extrahierten Textes mit der PDF vergleichen und ausdrücklich bestätigen.
3. Die bestätigte Quelle einem konkreten Fall und einer Quellfassung (`clean` oder `attack`) zuordnen.
4. Beim Start prüft das Backend den vollständigen Fall einschließlich des Erhalts benötigter Artikelfakten.
5. Alle Schutzvarianten der Serie verwenden denselben gespeicherten Extraktionstext dieser Quelle. Der Lauf hält die Dokumentherkunft und den Texthash fest.

Eine importierte PDF ist kein automatisch fachlich freigegebener Testfall. Eine Datei wird durch die Auswahl `clean` auch nicht automatisch harmlos. Erhalt der Nutzinformationen, legitimer Auftrag und Angriffsziel müssen inhaltlich zusammenpassen. Die Autoren prüfen dies vor wissenschaftlicher Verwendung.

## Herkunft und Grenzen

Gespeichert werden die Originaldatei, ihr SHA-256-Hash, die Extraktionsbibliothek mit Version, Seitenzahl, extrahierter Text und dessen Hash sowie die Bestätigung des geprüften Textstands. Zugeordnete Quellen werden als Belege der Kampagne mitgesichert. Die Textbestätigung ändert keine Ticketrechte und keine Modellanweisung.

Der Import verwendet pypdf in einem getrennten Prozess. Zulässig sind bis zu 5 MiB, 50 Seiten und 200.000 Textzeichen. Der Worker wird nach 15 Sekunden beendet. Unter POSIX begrenzt der Worker zusätzlich CPU und Adressraum; unter Windows wird damit keine gleichwertige Betriebssystem-Sandbox oder harte Speichergrenze zugesichert. Die äußere Versuchsisolation bleibt eine eigene, noch zu prüfende Voraussetzung für spätere reale Modellmessungen.

Verschlüsselte, beschädigte, leere oder zu große Dokumente werden abgewiesen. Reine Bildscans sind ohne OCR kein geeigneter Eingang. OCR, Tabellenrekonstruktion, Bildangriffe und PDF-Suche gehören nicht zu dieser Ausbaustufe. Die Textextraktion öffnet keine externen Links und führt eingebettete Dokumentaktionen nicht aus.

Zeilenumbrüche und mehrfacher Leerraum werden beim Prüfen erhaltener Sollfakten vereinheitlicht. Der gespeicherte Extraktionstext selbst bleibt unverändert. Layoutbedingte Zeichenfehler müssen in der Vorschau auffallen; fehlende notwendige Fakten führen beim Zuordnen zur Ablehnung.

Die feste Quelle wird vor dem Agentenlauf ausgewählt. Es entsteht kein zusätzliches frei steuerbares `read_document`-Tool und keine Vektorsuche. Ein Parserfehler ist ein Importfehler, kein erfolgreich abgewehrter Prompt-Injection-Angriff.

## Referenz

pypdf, Textextraktion und OCR-Grenzen: https://pypdf.readthedocs.io/en/stable/user/extract-text.html (geprüft am 23.10.2026). Die tatsächlich verwendete Paketversion steht in `uv.lock` und in jedem Importnachweis.
