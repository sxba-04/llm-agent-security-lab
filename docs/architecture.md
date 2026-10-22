# Architektur und Sicherheitsregeln

Das Labor führt Nutzeraufträge auf synthetischen Service-Tickets aus. Der externe Artikel ist die untersuchte Angriffsfläche. Eine Fallbeschreibung enthält außerdem vertrauenswürdige Sitzungsrechte und Bewertungsdaten. Diese Bereiche haben unterschiedliche Aufgaben und dürfen nicht vermischt werden.

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
