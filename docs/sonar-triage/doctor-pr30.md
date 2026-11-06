# PR 30: statische Einordnung der Diagnose-Portprobe

Stand: 2026-11-06. Geprüfte Fundstelle und Quellstand:
`6b48f567e708de55230029549fee7a27c06b3d93`. Diese Prüfung betrifft genau
die Sonar-Annotation
[AaGwHoAd3f6_aqzNEjCS](https://sonarcloud.io/project/issues?id=sxba-04_llm-agent-security-lab&issues=AaGwHoAd3f6_aqzNEjCS&pullRequest=30),
„Server-Side Request Forgery via faulty LLM-supplied CLI arguments in
doctor.port_check()“, `src/security_lab/doctor.py:85`.

**Urteil: `not_actionable`, hohe statische Sicherheit.** Die behauptete
Herkunft aus einem Modellaufruf entspricht keinem vorhandenen Aufrufpfad.
Die Begründung ist kein pauschaler Ausschluss lokaler Programme.

## Geprüfter Datenfluss und Grenze

- `doctor.main` nimmt den Port direkt aus dem vom Betriebssystem gestarteten
  Diagnose-CLI entgegen (`--port`, Integer, Bereich 1–65535; Zeilen 173–184
  des geprüften Stands). Die dokumentierte Nutzung erfolgt durch den
  Entwicklungsoperator, siehe `docs/setup-windows.md` und VS-Code-Diagnosetask.
- `diagnose` reicht diese Zahlen an `port_check` weiter. Dort ist die Zieladresse
  fest `127.0.0.1`, die Adressfamilie `AF_INET` und das Timeout 0,3 Sekunden
  (`doctor.py:82–85`). Nur `connect_ex` wird aufgerufen: keine DNS-Auflösung,
  keine HTTP-Anfrage, keine übermittelten Anwendungsdaten und kein durch den
  Portwert auswählbarer externer Host.
- Die Suche nach Aufrufern ergab keinen Import und keinen Aufruf von `doctor`
  durch FastAPI, Provideradapter oder Ausführungskern. Der Modellwerkzeugvertrag
  in `core.py:33–43` enthält ausschließlich `read_ticket` und `append_note`.
  `_syntax_error` verwirft andere Namen (`core.py:88–105`), bevor die beiden
  synthetischen In-Memory-Effekte ausgeführt werden (`core.py:183–209`).
- `SECURITY.md` verbietet Host- und Netzwerkzugriff durch Modellargumente und
  grenzt zugleich den Operator mit Zugriff auf dasselbe Betriebssystemkonto
  ab. `AGENTS.md` bestätigt den geschlossenen Werkzeugumfang. Die Prüfung
  fand keine abweichende, enger geltende `SECURITY.md`.

Ein Operator kann damit bewusst einen beliebigen lokalen Port auf Belegung
prüfen. Das ist die dokumentierte Diagnosefunktion unter seinen bestehenden
Betriebssystemrechten. Modellantworten, Artikel, PDF-Dateien und HTTP-Anfragen
erhalten dadurch weder einen CLI-Einstiegspunkt noch Netzwerkbefugnisse.
Die feste Loopback-Adresse bleibt unverändert; eine zusätzliche Einschränkung
auf einen einzigen Port würde die konkrete Scannerbehauptung nicht adressieren.

## Grenzen und Folgeschritt

Quelle der Meldung ist die GitHub-Annotation mit Titel, Zeile und Sonar-ID.
Ein weitergehender Sonar-Datenfluss war nicht verfügbar. Dies ist eine statische
Prüfung des angegebenen Stands, kein Laufzeit-PoC und keine vollständige
Sicherheitsprüfung der Anwendung. Eine künftig hinzugefügte Modell- oder
HTTP-Anbindung des Diagnosemoduls würde eine neue Bewertung erfordern.

Die konkrete Meldung kann mit diesem Datenfluss als Fehlalarm eingeordnet
werden. Diese Datei ändert keinen Sonar-Status, keine Regel und kein Quality
Gate. Separat wurden die gemeldeten Wartbarkeitsprobleme der Versionsdiagnose
behoben: begrenzte numerische Verarbeitung ohne regulären Ausdruck, kleinere
Versionsprüfungen und Entfernung der redundanten `SSLError`-Ausnahme.
