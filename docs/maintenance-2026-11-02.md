# Betriebs- und Qualitätsprüfung vom 2. November 2026

## Ausgangsstand

Die Prüfung startete auf `main` bei `5e192a2567cc9be33219247b8b4cc9aec4324662`.
Der Render-Service lief auf diesem Commit mit 0,5 CPU und 512 MB RAM in Frankfurt.
Der Betreiber hatte den kostenpflichtigen Compute-Plan selbst aktiviert.
Das Startprotokoll bestätigte weiterhin flüchtigen Speicher; eine persistente Disk
war weder im Servicezustand noch in seiner Ereignishistorie nachgewiesen.

Die [frische Sonar-Inventur, Versuch 2](https://github.com/sxba-04/llm-agent-security-lab/actions/runs/41260073281)
enthielt 177 offene Befunde auf diesem Analyse-Commit: 158 Code Smells,
18 vom Scanner als Vulnerability eingestufte Befunde und einen Bug.
Scanner-Kategorien sind keine Bestätigung ausnutzbarer Schwachstellen.
Die sieben vom Betreiber genannten Dependabot-Alerts konnten über den verfügbaren
GitHub-Connector nicht einzeln gelesen werden; deren Zuordnung bleibt offen.

Der [CI-Lauf des Ausgangsstands](https://github.com/sxba-04/llm-agent-security-lab/actions/runs/41362222737)
hatte ein bestandenes Sonar Quality Gate und folgende Coverage-Artefakte:

| Bereich | Zeilen | Zweige |
|---|---:|---:|
| Python | 89,28 % | 81,58 % |
| React | 88,96 % | 72,92 % |

Sonars zusammengefasste Messung beträgt 85,4 % Coverage; sie ist nicht mit
reiner Zeilenabdeckung gleichzusetzen. Der PDF-Extraktionsprozess läuft absichtlich
mit bereinigter Umgebung. Seine Zeilen werden durch die Coverage des Elternprozesses
nicht vollständig erfasst, obwohl Integrationstests echte PDFs prüfen.

## Änderungen und Nachweisgrenzen

- Veraltete interne Sitzungstoken nach einem Backend-Neustart erhalten einen
  eindeutigen Fehlercode. Die nächste bewusst ausgelöste Aktion lädt ein neues
  Sitzungstoken; Schreiboperationen werden nicht automatisch wiederholt.
- Verspätete Antworten einer alten Anmeldung dürfen eine neuere Anmeldung nicht
  abmelden oder deren Sitzungstoken ersetzen. Codeverlust bleibt eine getrennte
  Betreiberrotation, keine rekonstruierbare Passwortabfrage.
- Frontend-Zustandsansichten und Props wurden vereinfacht; unbekannte und offene
  Bewertungen bleiben ausdrücklich von negativen Ergebnissen getrennt.
- Lokale HTTP-Prüfungen wurden gegliedert und bestehende Fehlerantworten intern
  dokumentiert. Öffentliche OpenAPI-Endpunkte bleiben deaktiviert.
- `pypdf` wird auf 6.21.4 aktualisiert und diese Version auch als Untergrenze
  festgeschrieben. Bereits gespeicherte PDF-Originale und Extrakte werden nicht
  neu geschrieben; neue Extraktionen protokollieren die neue Parser-Version.
- Nach erfolgreicher Sonar-Analyse auf `main` entsteht künftig ein aktuelles,
  bereinigtes Befundinventar. Der manuelle Export bleibt verfügbar.
- Dokumentation, Branchschutz-Vorlage und Render-Vorlage wurden an den geprüften
  Betriebsstand angepasst. Das Wiki erhält vorbereitete Einstiegsseiten; deren
  Vorhandensein im Repository bedeutet keine Veröffentlichung im separaten Wiki.

Der lokale Gesamtbuild, Verhaltenstests und ein unabhängiger statischer
Code-/Security-Review dienen der technischen Prüfung. Maßgeblich für den Merge
sind zusätzlich die Pflichtprüfungen auf dem tatsächlichen PR-Kopf, einschließlich
Windows und Browserintegration. Fehlgeschlagene oder nicht verfügbare Prüfungen
werden nicht als bestanden ausgewiesen. Die tatsächliche Sonar-Restzahl ist nach
dem neuen Scan abzulesen; aus der Zahl geänderter Stellen wird sie nicht geschätzt.

Lokale Prüfung unter Linux/Python 3.12.14: 306 Python-Tests erfolgreich (ein
plattformspezifischer Skip), 43 React-Tests erfolgreich, TypeScript-/Vite-Build
erfolgreich und unabhängiger statischer Review ohne blockierenden Befund.
Die lokale Python-Umgebung enthielt dabei noch `pypdf 6.21.2`; das neu aufgelöste
Lockfile verlangt 6.21.4. Dessen Download und der Chromium-Download waren in
dieser Umgebung nicht erfolgreich. Die CI muss deshalb die aktuelle Lockdatei
einschließlich PDF- und Browserintegration auf Linux und Windows prüfen.
Die lokale React-Coverage beträgt 91,98 % Zeilen und 79,38 % Zweige; Änderungen
der Codeaufteilung beeinflussen neben zusätzlichen Tests auch deren Nenner.

## Noch ausstehende Betreiberentscheidungen

Der aktuelle Zugangscode wurde nicht ausgelesen, ersetzt oder in Dateien abgelegt.
Eine sichere Rotation muss bestehende, noch benötigte Zugänge berücksichtigen.
Ein Konto-Login mit externer Identität wäre ein eigenes Feature; die beiden
Betreiber teilen weiterhin Rechte und Workspace.

Eine persistente Disk ist ein zusätzlicher kostenpflichtiger Speicher. Vor ihrer
Einrichtung stehen die konkrete Kostenentscheidung und ein Export vorhandener
Belege; anschließend sind Schreib-, Neustart- und Wiederherstellungsprüfung nötig.
`LAB_STORAGE_MODE=persistent` allein stellt keinen dauerhaften Speicher bereit.
Siehe [Hosting](hosting.md) und [Dokumentationseinstieg](README.md).

Alle Änderungen sind KI-unterstützte Entwicklungsarbeit. Menschliche
Szenarienfreigabe, Gutachten und empirische Modellmessungen werden nicht dadurch
ersetzt. B/F/P/FP, der Mock-Modus der Oberfläche und die gesonderte Freigabe echter
Modellaufrufe bleiben erhalten.
