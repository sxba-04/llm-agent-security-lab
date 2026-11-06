# Frontend-Prüfung der Sonar-Meldungen zu PR 30

Stand: 6. November 2026. Ausgangsanalyse: Commit
`6b48f567e708de55230029549fee7a27c06b3d93`, PR 30. Die folgenden Angaben sind
eine Code- und Verhaltensprüfung, keine Behauptung über den Status einer späteren
Sonar-Analyse. Es wurden keine Regeln deaktiviert und keine `NOSONAR`- oder
Lint-Ausnahmen eingefügt.

## Korrigierte Stellen

- Benannte native `section`-Elemente ersetzen nachgebildete Regionen. Die gemeinsame
  Komponente `ScrollRegion` wird für Tabellen, JSON, Quellen und längere Texte
  verwendet. Die `pre`-Struktur bleibt für vorformatierten Inhalt erhalten.
- Native `output`-Elemente ersetzen zusätzliche `status`-Rollen bei Speicher- und
  Metadatenmeldungen. Inhalt, Live-Status und zugängliche Namen bleiben erhalten.
- Die mobile Fokus- und Navigationslogik liegt in `mobile-navigation.ts`, getrennt
  von Datenabfrage und Seitendarstellung. Die sichtbare Navigation und ihre
  Tastaturregeln bleiben gleich.
- Theme-Auswahl und Tests verwenden eine einfache Systemfarbzuweisung beziehungsweise
  konkrete Längenassertionen.

## Fokus auf scrollbaren Belegen bleibt erforderlich

Die bisherigen `tabIndex`-Meldungen betrafen die Vergleichs-, Versuchs- und
Bewertungstabellen sowie JSON-, Text- und Quellansichten:

| Bisherige Sonar-ID | Stelle |
|---|---|
| `AaGwHn_53f6_aqzNEjB5`, `AaGwHn_53f6_aqzNEjB7` | Vergleichstabellen |
| `AaGwHoAH3f6_aqzNEjCB` | Versuchsverlauf |
| `AaGwHn_w3f6_aqzNEjB2` | Bewertungsübersicht |
| `AaGwHn_m3f6_aqzNEjBv`, `AaGwHn_m3f6_aqzNEjBx`, `AaGwHn_m3f6_aqzNEjBz` | JSON, Text, Quellen |

Die gemeinsame native Region besitzt weiterhin `tabIndex={0}`. Sie ist eine
bedienbare Scrollfläche: lange Belege oder breite Tabellen werden durch
`overflow:auto` innerhalb des Bereichs begrenzt. Ohne Fokus können Tastaturnutzer
den abgeschnittenen Inhalt nicht in allen unterstützten Browsern erreichen.
Die erste tatsächliche Firefox/axe-Prüfung meldete genau diese fehlende
Tastaturbedienbarkeit an JSON-Belegen. Entfernen des Fokus würde den behobenen
Barrierefreiheitsfehler wieder einführen. Die Region hat einen zugänglichen Namen,
einen sichtbaren Fokusrahmen und keinen positiven Tab-Index. Diese konkrete Stelle
benötigt daher eine Einzelbewertung, falls Sonar sie erneut beanstandet.

Referenz: [MDN: overflow – Accessibility](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/overflow#accessibility).
Die bestehenden automatisierten Prüfungen stehen in
`frontend/e2e/accessibility.spec.ts`, `frontend/e2e/mobile.spec.ts` und
`frontend/src/theme-navigation.test.tsx`.

## Responsive Navigation mit ARIA-Dialog

Meldung `AaGwHn_93f6_aqzNEjB9` empfiehlt ein natives `dialog`. Der gleiche
Navigationsbereich ist auf dem Desktop eine dauerhaft sichtbare Seitenleiste
und auf kleinen Bildschirmen eine zeitweilige modale Navigation. Die modale
Rolle, der Name und `aria-modal` werden ausschließlich im geöffneten mobilen
Zustand gesetzt. Die geschlossene mobile Navigation ist `inert` und ausgeblendet.
Beim Öffnen erhält der aktive Navigationslink Fokus; Tab/Shift+Tab bleiben im
Bereich. Escape und der sichtbare Schließen-Knopf schließen ihn und stellen den
Fokus wieder her. Eine abgeschlossene Navigation setzt Fokus in den neuen Inhalt.
Der Hauptinhalt ist währenddessen `inert`, die Hintergrundfläche schließt das Menü.

Dies ist eine gezielt implementierte ARIA-Dialogvariante gemäß dem
[WAI-ARIA-Dialogmuster](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/).
Ein Wechsel zu `showModal()` würde zusätzlich Top-Layer-, Inert- und
Fokusverhalten ändern und ist keine notwendige Fehlerkorrektur an dieser geprüften
Navigation. Die Empfehlung wird deshalb als begründete Implementierungsentscheidung
beibehalten; sie ist keine pauschale Freistellung anderer Dialoge. Eine vollständige
manuelle Screenreader-Abnahme wird dadurch nicht behauptet.

## Plattformgebundene Bildreferenzen

Meldung `AaGwHoAJ3f6_aqzNEjCE` betrifft den ausdrücklich begründeten Plattform-
Skip in `frontend/e2e/visual.spec.ts`. Die Bildreferenzen gelten für Linux mit
Chromium: Betriebssysteme rendern Schriftarten unterschiedlich. Der Kommentar
und die Skip-Begründung nennen diese Grenze. Linux-CI führt beide Bildvergleiche
für Hell und Dunkel aus; Windows führt weiterhin die funktionalen und
automatisierten Barrierefreiheitsprüfungen aus. Auf der Referenzplattform wird
kein Bildvergleich übersprungen. Der gezielte Plattform-Skip bleibt erhalten.

## GitHub-Anmeldeziel

Meldung `AaGwHn_y3f6_aqzNEjB3` bezeichnet `window.location.assign()` in
`AccessGate.tsx` als unbereinigte Weiterleitung. Der vollständige Datenfluss ist:

1. `GitHubSessions.start()` im Backend erstellt das Ziel aus dem festen Präfix
   `https://github.com/login/oauth/authorize` und kontrollierten OAuth-Parametern.
2. `publicAuthRequest()` verwendet im gehosteten Modus die konfigurierte
   Backend-Origin; der Vite-Build erzwingt hierfür HTTPS.
3. `authorizationTarget()` prüft bereits vor der Navigation den exakten GitHub-Origin
   und Pfad, fehlende URL-Zugangsdaten/Fragmente, State, PKCE-Challenge und S256,
   die Laufzeit sowie die Rückleitung auf die aktuelle Frontendseite.
4. Erst nach erfolgreicher Prüfung speichert der Browser kurzlebigen PKCE-Zustand
   und navigiert; API-/Labortoken werden nicht in diese URL übernommen.

Damit war die behauptete unkontrollierte externe Weiterleitung im geprüften Pfad
nicht nachgewiesen. Ergänzend werden jetzt doppelte OAuth-Parameter abgelehnt, damit
Browser und Provider nicht unterschiedliche Werte desselben Parameters auslegen.
Das endgültige Ziel wird nach den Prüfungen aus dem festen GitHub-URL-Literal neu
aufgebaut; aus der Antwort werden nur die zuvor geprüften Queryparameter übernommen.

`frontend/src/github-auth.test.tsx` prüft zusätzlich falsches Protokoll, ähnliche
Fremddomäne, anderen Pfad, Benutzername, Passwort, abweichenden Port, Fragment und
doppelte State-/Redirect-/PKCE-Parameter mit ansonsten gültigen Ausgangsdaten.
Abgelehnte Ziele erzeugen keinen gespeicherten PKCE-Zustand. Bestehende Tests für
Statebindung, PKCE, Ablauf, Rückkehr, Kontosperre und Code-Fallback bleiben erhalten.

Lokale Prüfung nach diesen Änderungen: 107 Frontend-Tests und Produktionsbuild
bestanden. Der Linux-Firefox-Lauf bestand alle 13 funktionalen Browserprüfungen,
einschließlich axe in beiden Themes, Tastaturbedienung und vier Fensterbreiten;
zusätzlich wurden zwei Quellenansichten zur Sichtprüfung aufgenommen. Diese
Aufnahmen ersetzen nicht den Chromium-Bildvergleich. Alle sechs Hosted-Firefox-
Prüfungen bestanden ebenfalls, einschließlich GitHub-Callback, abgelehntem Konto,
Sitzungswiderruf/Abmeldung und axe auf Anmeldung/Sitzungsmenü in beiden Themes.
Die GitHub-Antworten dieser lokalen HTTPS-Fixtures sind synthetisch; dies ist kein
neuer Live-Login-Nachweis. CI-/Sonar-Ergebnisse des finalen Commits werden im
allgemeinen Änderungsnachweis separat festgehalten.

## Erneute Analyse auf `90667b5`

Die Analyse vom 6. November 2026, 09:37:16 UTC, enthält nach den Korrekturen
noch drei der hier geprüften Frontend-Meldungen. Der Befund zur gemeinsamen
Scrollregion hat nun die ID `AaGwOUR7RVlkm00GzpSU` (`typescript:S6845`);
die übrigen IDs bleiben `AaGwHoAJ3f6_aqzNEjCE` (`typescript:S1607`) und
`AaGwHn_y3f6_aqzNEjB3` (`tssecurity:S6105`).

Der OAuth-Flow zeigt API-Antwort, `startGitHubLogin()` und
`window.location.assign()`, berücksichtigt aber die dazwischenliegende
Prüfung und Neukonstruktion in `authorizationTarget()` nicht als Bereinigung.
An der Navigationsstelle kann weiterhin ausschließlich der feste HTTPS-Origin
und Pfad von GitHub verwendet werden. Die übernommenen Queryparameter können
den Origin oder Pfad des bereits erzeugten URL-Objekts nicht ersetzen.
Die im vorigen Abschnitt genannten Gegenbeispiele werden abgelehnt, bevor
Anmeldezustand gespeichert wird. Die Bewertung gilt für diesen konkreten
Aufrufpfad; beliebige andere API-Weiterleitungen werden damit nicht freigestellt.

Auf diesem Commit bestanden beide Chromium-Bildvergleiche unter Linux und
die funktionalen Browserprüfungen unter Windows und Linux. Der begründete
Windows-Skip und die per Tastatur erreichbare Scrollregion bleiben erhalten.
Der gesonderte Python-Hinweis `python:S5778` betrifft einen Testaufbau und wird
durch Konstruktion des Fake-Clients vor dem erwarteten Fehleraufruf behoben.
Keiner dieser Nachweise ersetzt das anschließende Quality-Gate-Ergebnis.
