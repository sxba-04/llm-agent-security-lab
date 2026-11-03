# Architektur und Sicherheitsregeln

Das Labor führt Nutzeraufträge auf synthetischen Service-Tickets aus. Der externe Artikel ist die untersuchte Angriffsfläche. Eine Fallbeschreibung enthält außerdem vertrauenswürdige Sitzungsrechte und Bewertungsdaten. Diese Bereiche haben unterschiedliche Aufgaben und dürfen nicht vermischt werden.

## Verzeichnisstruktur und Modulgrenzen

Das Repository enthält ein installierbares Python-Paket und einen separat gebauten Browserclient. `src/security_lab/` ist ein Python-`src`-Layout: Unterhalb von `src` liegt der importierbare Paketname, während Projektkonfiguration und Tests außerhalb des Pakets bleiben. `pyproject.toml` legt dieses Layout ausdrücklich für die Paketinstallation fest. Das Backend fehlt also nicht; es ist Teil dieses gemeinsamen Pakets.

| Pfad / Module | Verantwortung |
|---|---|
| `src/security_lab/core.py`, `models.py`, `contracts.py`, `cases.py` | Versuchskern, Datenverträge und validierte synthetische Fälle |
| `providers.py`, `budget.py` | Kontrollierter Modelladapter und Kostenbegrenzung |
| `batch.py`, `jobs.py` | Serienausführung, Zustände und Unterbrechungen |
| `evaluation.py`, `comparisons.py`, `review.py` | Gemeinsame technische Auswertung, gepaarte Vergleiche und menschliche Urteile |
| `documents.py`, `sample_pdf.py`, `archives.py` | PDF-Quellen, Beispiel-PDFs und verifizierbare Belegarchive |
| `server.py`, `hosted.py` | FastAPI-Schnittstelle und zusätzliche gehostete Zugriffsgrenze |
| `cli.py`, `web_cli.py`, `hosted_cli.py`, `__main__.py` | Getrennte Startwege für CLI, lokale Werkbank und expliziten Hostingbetrieb |
| `frontend/src/` | React-/TypeScript-Seiten, API-Client, Gestaltung und komponentennahe Tests |
| `frontend/e2e/`, `frontend/e2e-hosted/` | Browserprüfungen für lokalen beziehungsweise HTTPS-Hostingbetrieb |
| `tests/` | Python-Regressions- und Integrationstests mit synthetischen Daten |
| `cases/dev/`, `cases/test/` | Entwicklungsfälle und getrennt vorgesehener Haupttestkatalog |
| `configs/` | Versionierte Vorlagen; keine echten Zugangsdaten |
| `scripts/`, `analysis/` | CI-Hilfen, Befundinventur und Tabellenexport |
| `docs/`, `.github/`, `.vscode/` | Dokumentation, automatisierte Prüfungen und gemeinsame IDE-Aufgaben |
| `pyproject.toml`, `uv.lock` | Python-Paket, optionale Webabhängigkeiten und aufgelöste Versionen |
| `frontend/package.json`, `frontend/package-lock.json` | Eigener Node-/Vite-Build und dessen aufgelöste Versionen |
| `render.yaml` | Beschreibung des Render-Dienstes; Live-Einstellungen werden derzeit direkt in Render verwaltet |

Ein Umbenennen von `src/` in `backend/` würde Importe, Paketbau, CI, IDE-Aufgaben und Deploymentpfade berühren. Es löst hier kein konkretes Problem: Der Python-Code ist zugleich Backend, Kommandozeilenanwendung und Auswertungsbibliothek. Daher bleiben diese Pfade bestehen.

Sinnvolle spätere Aufteilungen folgen fachlichen Verantwortlichkeiten. Beispielsweise können wachsende HTTP-Routen in ein Unterpaket `security_lab/web/` ausgelagert werden, wenn dies konkrete Komplexität reduziert. Dabei bleiben öffentliche Imports, Startbefehle und gemeinsame Auswertungslogik kompatibel; eine solche Änderung wird separat mit API- und Browserprüfungen umgesetzt. Reine Verzeichnisverschiebungen und eine gleichzeitige Änderung der Versuchsmethode sollten nicht in denselben Umbau fallen.

Generierte Builds, virtuelle Umgebungen, Coverage und persönliche Laufdaten gehören weiterhin nicht in die Quellcodehistorie. Wissenschaftliche Belege werden als geprüfte Archive mit ihrem Code- und Konfigurationsstand gesichert. Das [Dokumentationsverzeichnis](README.md) ist der Einstieg für Betrieb und Entwicklung; ein Wiki kann darauf verweisen.

## Daten und Verantwortlichkeiten

| Bestandteil | Aufgabe und Vertrauensgrenze |
|---|---|
| Fall und Sitzungsrechte | Legen legitimen Auftrag, Identität, lesbare Tickets und Schreibfreigabe fest |
| Artikel | Wird als externe, nicht vertrauenswürdige Quelle an das Modell weitergegeben |
| Modelladapter | Liefert Antwort oder Toolvorschläge; entscheidet keine Zugriffsrechte |
| Tool-Gateway | Prüft Syntax, gegebenenfalls F und P und führt zugelassene Aktionen aus |
| Synthetisches Backend | Enthält für jeden Lauf eine frische Kopie der Tickets |
| Ereignisprotokoll | Hält Vorschläge, Entscheidungen und tatsächlich eingetretene Wirkungen auseinander |
| Auswertung | Prüft Ereignisse und Zustände anhand unabhängiger Sollregeln |

`read_ticket` liest einen Datensatz. `append_note` ergänzt einen Text in einem Ticket. Beide Werkzeuge gehen durch dieselbe Prüfstelle. Es gibt keine frei adressierbaren Netzwerk-, Dateisystem- oder Shell-Tools.

## Ein Aufgabenlauf

1. Fall laden und validieren; Artikelversion und Schutzvariante auswählen.
2. Frischen Backendzustand, Sitzungsrechte und Dialog anlegen.
3. Artikel an der vorgesehenen Eingabestelle durch F prüfen, wenn F aktiv ist.
4. Das Modell um eine Antwort oder einen Toolvorschlag bitten.
5. Vorschläge vor einer Blockierung protokollieren und ihre Syntax prüfen.
6. Textinhalte durch F und anschließend die Berechtigung durch P prüfen, soweit die jeweilige Variante dies aktiviert.
7. Zugelassene Aktionen im synthetischen Backend ausführen; Toolantworten vor Übergabe an das Modell durch F prüfen.
8. Bei einer weiteren Modellanfrage den tatsächlichen Übergang geschützter Daten in den Modellkontext erfassen.
9. Endgültige Ausgabe durch F prüfen; Ausgabe, Endzustand und Laufstatus speichern.

Bei mehreren Toolvorschlägen wird jeder einzelne geprüft. Ein Abbruch löscht bereits eingetretene Wirkungen nicht aus dem Protokoll.

## Varianten und feste Bedingungen

| Bedingung | B | F | P | FP |
|---|---|---|---|---|
| Grundlegende Syntaxprüfung | Ja | Ja | Ja | Ja |
| Inhaltsfilter | Nein | Ja | Nein | Ja |
| Autorisierung vor Backendwirkung | Nein | Nein | Ja | Ja |
| Laufgrenzen und synthetische Daten | Ja | Ja | Ja | Ja |

Systemprompt, Toolbeschreibungen und Modellkonfiguration bleiben bei einem Vergleich gleich. Bei FP steht der Filter vor der Autorisierung. In B und F darf das Backend bewusst auch gesperrte synthetische Tickets bedienen. Andernfalls würde eine zusätzliche, versteckte Zugriffssperre den gemessenen Effekt von P überlagern.

## Autorisierung P

- Eine gültige Sitzungsidentität muss vorhanden sein.
- Lesende Zugriffe sind nur auf ausdrücklich freigegebene Ticket-IDs erlaubt.
- Schreiben setzt den Schreibmodus und die Freigabe des betreffenden Zieltickets voraus.
- Fehlende oder ungültige Freigaben werden abgelehnt.

Diese Rechte stammen aus der Fallkonfiguration. Artikel und Modellvorschläge können sie nicht erweitern. Die Formulierung einer angeblichen Administratorfreigabe im Artikel erzeugt daher keine Berechtigung.

## Inhaltsfilter F

F ist ein transparentes regelbasiertes Paket für Artikel, Textinhalte von Toolvorschlägen, Toolantworten und endgültige Antworten. Der Filter kennt keine fallspezifischen Geheimwerte oder Erfolgskriterien. Objektberechtigungen gehören zu P.

Eine Blockierung erzeugt eine protokollierte Rückmeldung. Die Anwendung kann innerhalb ihrer Grenzen weiterarbeiten. Generische Regeln können sowohl Angriffe übersehen als auch harmlose Texte blockieren. Die Entwicklungsfälle enthalten deshalb auch harmlose verdächtig wirkende Formulierungen.

F umfasst mehrere Eingriffspunkte. Der Vergleich B/F/P/FP erlaubt keine getrennte Wirkungsbehauptung über Eingabe- und Ausgabefilter.

## Beobachtbarkeit

Ein unzulässiger Modellvorschlag, ein ausgeführter Backendzugriff, die Übergabe gelesener Daten an das Modell und deren Anzeige für den Nutzer sind verschiedene Ereignisse. Ein Filter auf einer Toolantwort kann eine Kontextoffenlegung verhindern, obwohl der unzulässige Backendzugriff bereits stattgefunden hat.

Synthetische Prüfwerte werden ausschließlich in geschützten Testdatensätzen erzeugt. Sie stehen nicht schon im Artikel oder im anfänglichen Systemprompt. Damit lässt sich ihre Herkunft im Verlauf nachprüfen.

## Grenzen

P schützt die definierten Objekt- und Operationsgrenzen. Eine erlaubte Notiz kann trotzdem eine falsche Aussage enthalten. Dieses Problem wird als G3 separat untersucht.

Die Modell-API ist Infrastruktur für Inferenz und kein Werkzeug, das das Modell frei steuern kann. Der Anwendungscode begrenzt die verfügbaren Werkzeuge, ersetzt jedoch keine überprüfte äußere Sandbox. Die Prüfung von Betriebssystemisolation und Netzwerkgrenzen bleibt ein eigener Einrichtungsschritt.

## Weboberfläche und PDF-Quellen

React/TypeScript ist die Bedienoberfläche für den lokalen und den explizit gehosteten Betrieb. FastAPI prüft Eingaben und ruft die bestehenden Python-Funktionen auf. Ein kleiner Jobmanager erlaubt genau eine aktive UI-Serie; Fortschritt und Ergebnisse stammen aus gespeicherten Manifesten und Records. Der Browser entscheidet keine Berechtigung und keine Erfolgsbewertung. Die CLI bleibt unabhängig von den optionalen Webpaketen verwendbar.

Der Standardstart liefert Frontend und API vom selben Loopback-Dienst aus. Host-/Origin-Prüfung und ein Token auf schreibenden Anfragen begrenzen Zugriffe fremder Webseiten; vom Browser frei wählbare Dateisystempfade gibt es nicht. Dieser Standardstart bleibt ein lokales Einzelbenutzersystem ohne Netzwerkfreigabe oder Loginverwaltung. Der getrennte Hostingstart verwendet eine öffentliche HTTPS-API mit zufälligen Betreiber-Zugangscodes oder freigegebenen GitHub-Konten und eigenen widerrufbaren Laborsitzungen. Aufbau und Speichergrenzen stehen in [hosting.md](hosting.md), die Identitäts- und Sitzungsgrenzen unter [GitHub-Anmeldung](github-login.md).

Eine PDF wird im separaten Extraktionsprozess in Text überführt. Der Import speichert das Original und die Extraktionsnachweise. Nach Vorschau und Bestätigung kann der Text einer festen Fallquelle zugewiesen werden. Die Kampagne übernimmt eigene Quellenbelege. Das Ereignis `document_provided` und das Ergebnisfeld `document_source` halten Identität, Herkunft und tatsächlichen Texthash fest. Diese Auswahl ist anwendungsseitig festgelegt; die zwei Agententools bleiben unverändert.

Der Artikel bleibt eine als nicht vertrauenswürdig gekennzeichnete externe Quelle in einer getrennten Kontextnachricht. PDF-Verarbeitung führt keine andere Rollenprivilegierung ein. Derselbe Quellentext wird in B/F/P/FP vor der jeweils vorgesehenen Inhaltsfilterung bereitgestellt.

## Unterbrechung und Evidenz

Ein Bedienabbruch wird vor Modellanfragen, nach empfangenen Antworten und vor weiteren Toolwirkungen berücksichtigt. Er kann einen bereits laufenden externen Transport nicht rückwirkend zurücknehmen. Alle zuvor beobachteten Vorschläge und Wirkungen bleiben erhalten; `cancelled` zählt nicht als gültiger Erfolg oder erfolgreiche Abwehr.

Bereits empfangene, aber fehlerhafte Modellantworten werden von fehlgeschlagenen Übertragungen getrennt. Verwertbare Verbrauchsdaten werden abgerechnet; begrenzte rohe Belege bleiben erhalten. Ungültige Toolargumente gelangen nicht zur Ausführung. Bei einem Fehler nach empfangener Antwort wird eine belegte Kontextübergabe nicht als sicher verhindert ausgegeben.
