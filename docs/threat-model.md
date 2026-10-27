# Bedrohungsmodell des lokalen Labors

Stand: 27. Oktober 2026. Dieses Dokument beschreibt die vorhandene Architektur und ihre Prüfziele. Es bestätigt keine vollständige Absicherung. Die verbindlichen Sicherheitsinvarianten und der Bewertungsmaßstab für Befunde stehen in [SECURITY.md](../SECURITY.md).

## System und Schutzgüter

Die Anwendung besteht aus einer lokalen React-Oberfläche, einem FastAPI-Dienst, dem gemeinsamen Python-Versuchskern und lokalen Belegdateien. Der reguläre Webstart verwendet einen Prozess auf `127.0.0.1`. Eine Anmeldung oder Trennung verschiedener Betriebssystemnutzer wird nicht angeboten. Die GUI führt ausschließlich Mock-Läufe aus; ein echter Modellzugang existiert nur als gesondert aktivierte CLI-Betriebsart.

| Schutzgut | Warum es geschützt werden muss |
|---|---|
| Rechner, lokale Dateien und Zugangsdaten | Artikel, Modellantworten und importierte Dateien dürfen keine Hostberechtigungen erlangen. |
| Tickets und Sitzungsrechte | Rechte stammen aus dem vertrauenswürdigen Fall, nicht aus einer angeblichen Freigabe im Artikel. |
| Laufdaten, PDF-Quellen und Bewertungen | Nachträgliche Verwechslung, Verlust oder Veränderung würde Ergebnisse und Reproduzierbarkeit verfälschen. |
| Vergleichbarkeit der Varianten | Zusätzliche versteckte Schutzmaßnahmen oder unterschiedliche Ausgangsdaten würden den Effekt von F/P überlagern. |
| API-Budget | Ein echter Versuch darf nur ausdrücklich und innerhalb der konfigurierten lokalen Grenzen starten. |

## Datenfluss und Vertrauensgrenzen

| Übergang | Eingabe und Verantwortung | Zu prüfende Grenze |
|---|---|---|
| Betreiber → Fallkonfiguration → Versuchskern | Der validierte Fall enthält Auftrag, Sitzungsrechte, Ausgangstickets und Sollbewertung. | Artikel und Modell dürfen diese vertrauenswürdigen Rechte nicht überschreiben; pro Lauf entsteht ein frischer Zustand. |
| PDF → Extraktionsprozess → bestätigter Artikel | Der Betreiber wählt eine Datei; ihre Bytes und Inhalte bleiben nicht vertrauenswürdig. | Begrenzte Extraktion, keine geerbten Provider-Schlüssel, überprüfbare Original-/Texthashes und Bestätigung des konkreten Textstands. |
| Ausgewählter Artikel → Modellkontext | Die Anwendung stellt eine feste Quelle bereit, gegebenenfalls nach F. | Der externe Text erhält keine Systemrolle. Alle verglichenen Varianten beginnen mit derselben ausgewählten Quelle. |
| Modellvorschlag → Gateway → synthetische Tickets | Das Modell liefert Daten und Vorschläge für `read_ticket` oder `append_note`. | Syntaxprüfung immer; F und P entsprechend der Variante. Keine Shell-, Datei-, Browser- oder frei adressierbaren Netzwerktools. |
| Browser → lokale HTTP-Schnittstelle | Die Oberfläche liest Ergebnisse und löst Bedienaktionen aus; eine fremde Webseite kann ebenfalls Anfragen versuchen. | Host-/Origin-Prüfung, Token für Änderungen, begrenzte Eingaben und verwaltete Pfade. Die GUI kann keine bezahlten Läufe aktivieren. |
| Ereignisse → Records/Manifest → Bewertungen/Archive | Ausführung und beobachtete Wirkungen bilden die Grundlage späterer Auswertungen. | Originalbelege erhalten; Zuordnungen, Hashes und Versionsketten prüfen; beschädigte oder unvollständige Daten nicht als vollständige Ergebnisse ausgeben. |
| Expliziter CLI-Aufruf → Modellanbieter | Nur diese Betriebsart liest einen API-Schlüssel und verwendet den festen Provider-Endpunkt. | Freigabeschalter, validierte Konfiguration, Budgetreservierung und sichere Behandlung fehlerhafter Antworten. |

Die Anwendung verwendet für B/F/P/FP denselben Ablauf. F prüft Inhalte an mehreren Stellen; P entscheidet vor einer Backendwirkung über die vertrauenswürdigen Sitzungsrechte. Die Auswertung berechnet ihre Feststellungen unabhängig von diesen Entscheidungen.

## Angreifer und beobachtbare Wirkungen

Der untersuchte Angreifer verändert den Wissensartikel. Er versucht, einen unzulässigen synthetischen Lesezugriff (G1), eine unzulässige Notiz (G2) oder eine falsche Aussage in einer erlaubten Antwort/Notiz (G3) zu bewirken. Ein Vorschlag ist noch keine ausgeführte Aktion. Backendzugriff, Übergabe an den Modellkontext und Anzeige für den Nutzer werden getrennt protokolliert.

Unabhängig von diesem Versuchsangreifer berücksichtigt die Implementierungsprüfung manipulierte PDF-/ZIP-Dateien, fehlerhafte Modellantworten, fremde Webseiten und veränderte Belegdateien. Ein Angriff auf diese Infrastruktur ist nicht durch eine absichtlich schwache Versuchsvariante gerechtfertigt.

In B und F ist P absichtlich deaktiviert. Ein dort erlaubter Zugriff auf ein gesperrtes synthetisches Ticket kann deshalb das erwartete Messergebnis sein. Eine Zugriffssperre in P/FP muss dagegen wirken. Die regelbasierte Inhaltsprüfung verspricht weder allgemeine Erkennung aller Prompt Injections noch semantische Korrektheit erlaubter Notizen.

## Annahmen und noch offene Nachweise

- Die Anwendung wird durch die Autoren auf ihren lokalen Rechnern mit synthetischen Daten betrieben. Eine Netzwerkfreigabe, zusätzliche Agententools oder ein Mehrbenutzerbetrieb wären Änderungen dieses Modells.
- Betriebssystemkonto und Arbeitsverzeichnis bilden keine voneinander isolierten Mandanten. Hashes sind keine digitale Signatur gegen einen Angreifer, der Belege und Prüfwerte gemeinsam ersetzen kann.
- Metadaten beschleunigen die Kampagnenliste. Sie ersetzen beim Öffnen nicht die vollständige Belegprüfung und verhindern keine beliebigen Dateisystem-Rennen.
- Der PDF-Unterprozess ist keine allgemeine Sandbox. Unter Windows fehlt weiterhin eine harte Prozess-Speichergrenze; die äußere Isolation vor echten Modellversuchen ist noch gesondert nachzuweisen.
- Ein lokales Budgetprotokoll ist nicht automatisch zwischen Rechnern geteilt und garantiert keine Obergrenze der Anbieterrechnung.
- Getrennte Bewertungsansichten unterstützen unabhängige Urteile, verhindern aber keinen Zugriff auf andere lokale Rohdateien. Wissenschaftliche Autorenabnahme und echte menschliche Bewertungen bleiben erforderlich.

Diese Grenzen sind Prüfkontext, keine pauschale Freistellung von Sicherheitsbefunden. Weitere Abläufe beschreiben [Architektur](architecture.md), [PDF-Quellen](pdf-sources.md), [Archive](archives.md) und [Modellzugang](api.md).
