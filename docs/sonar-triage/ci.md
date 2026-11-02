# Einzelprüfung der 19 Sonar-CI-Befunde

Inventurstand: `12db393771b70f05f12f947fe213c43084a0fce5`; Patchbasis: `3731bcd9a86fd98aca9c8168c9b1bf8065b44d62`.

Korrigierte Einordnung vom 02.11.2026: 15 Befunde wurden durch den damaligen Patch adressiert; zwei S7689-Fundstellen sind kontextuelle False Positives und zwei berechtigte Wartbarkeitshinweise bleiben offen. Eine gemeldete Regelverletzung wird nicht mit einer tatsächlich kompromittierten Abhängigkeit gleichgesetzt. Es wurden keine Sonar-Befunde remote geschlossen und keine Regeln oder Dateipfade ausgeschlossen.

Patch-Commit: `60c7ffeac15b1db47b8aa550a2b31dff65cf17ce`. Diff-SHA-256: `ca28ba9ab56a1c209b206475e4855de7c47be21e2356415c746539d2dd8c0d65`. Dies war der lokale Prüfstand vom 01.11.2026; die folgenden damaligen Prüfergebnisse und Hashes werden als Herkunftsnachweis bewahrt. Sie beschreiben nicht den heutigen Veröffentlichungsstatus.

## Korrektur zu S7689 am 2. November 2026

Die bisherige Erklärung zur Commit-Provenienz war für diese Regel falsch.
Sonars [offizielle Release Notes](https://docs.sonarsource.com/sonarqube-server/2026.1/server-update-and-maintenance/lta-to-lta-release-notes)
beschreiben S7689 als Regel für Shell-Kommandosubstitution mit Backticks.
Beide Fundstellen gehören zu `shell: python {0}`; die Backticks stehen in
Python-Strings und formatieren Markdown-Ausgabe. Die neue Quellprüfung bewertet
sie daher als kontextuelle False Positives. `git rev-parse HEAD` liefert weiterhin
den ausgecheckten Commit, beseitigt aber keine Shell-Kommandosubstitution an
diesen Fundstellen.

Die 19 historischen Inventur-IDs und ihre Originalpositionen bleiben erhalten.
[ci.json](ci.json) bewahrt bei den zwei korrigierten Einträgen zusätzlich die
frühere Bewertung. Die unveränderte [summary.json](summary.json) ist die damalige
Zusammenführung vor dieser Korrektur, keine aktuelle Gesamtauswertung.
Der [Snapshot vom 02.11.2026](README.md) enthält zwei neue S7689-IDs an denselben
Python-Ausgabestellen; diese werden nicht nachträglich in die alte 19er-Inventur
aufgenommen. Kein Remote-Befund wurde durch diese Korrektur geändert.

## Einzelbewertungen

| ID | Regel / Quelle | Einordnung / Stand | Begründung |
|---|---|---|---|
| `AaGMS_8y7rRJBvbBA1nZ` | `githubactions:S8541`, `.github/workflows/pages.yml:36` | valid_hardening; patch_prepared_pending_ci_and_rescan | Pages: pip installiert zwar uv==0.12.23, verbietet aber keinen Sdist-Fallback. Der geprüfte Linux-Lauf erhielt bereits ein Wheel; ein schädlicher Build wurde nicht beobachtet. --only-binary=:all: macht den Wheel-Zwang ausdrücklich und lässt eine fehlende Binärdistribution sicher scheitern. |
| `AaGMS_8y7rRJBvbBA1na` | `githubactions:S8541`, `.github/workflows/pages.yml:37` | valid_hardening; patch_prepared_pending_ci_and_rescan | Pages: --locked schützt Versionsauflösung und Lockdatei, untersagt jedoch keine Build-Backends fremder Sdists. --no-build ergänzt diese Grenze. uv 0.12.23 erlaubt dabei weiterhin den benötigten, überprüfbaren lokalen Editable-Build; Drittanbieter-Builds werden nicht pauschal freigegeben. |
| `AaGMS_8y7rRJBvbBA1nb` | `githubactions:S6505`, `.github/workflows/pages.yml:38` | confirmed_install_hook_exposure; patch_prepared_pending_ci_and_rescan | Pages: npm ci erzwingt package-lock.json, führte aber standardmäßig Installationsskripte der Pakete aus. npm ci --ignore-scripts behält den Lock-Zwang und unterbindet diese Hooks. Frische Installation, 31 React-Tests und Produktionsbuild funktionieren ohne Ausnahme für einzelne Pakete. |
| `AaGMS_8y7rRJBvbBA1nc` | `githubactions:S6505`, `.github/workflows/pages.yml:50` | conditional_risk_hardened; patch_prepared_pending_ci_and_rescan | Pages: npx playwright benutzt nach erfolgreichem npm ci hier die lokale, gesperrte Installation. Ein zusätzlich heruntergeladenes Paket wurde nicht nachgewiesen. Bei fehlender lokaler CLI besitzt npx dennoch einen Installationspfad samt Hooks. Der direkte Node-Aufruf der installierten @playwright/test/cli.js entfernt diesen impliziten Paketinstallationspfad. |
| `AaGMS_8y7rRJBvbBA1nd` | `githubactions:S8543`, `.github/workflows/pages.yml:50` | conditional_risk_hardened; patch_prepared_pending_ci_and_rescan | Pages: derselbe npx-Aufruf kann generell auf eine nicht im Projekt installierte Paketversion ausweichen. Der konkrete erfolgreiche Installationspfad verwendete bereits die Lockdatei. Direkter Aufruf der ausdrücklich deklarierten @playwright/test-CLI bindet die Ausführung an genau deren installierte Version und scheitert bei fehlender Datei. |
| `AaGMS_8z7rRJBvbBA1ne` | `githubactions:S8541`, `.github/workflows/mock-campaign.yml:45` | valid_hardening; patch_prepared_pending_ci_and_rescan | Manuelle Mock-Kampagne: die uv-Version ist fest, aber pip erlaubte einen Sdist-Fallback. --only-binary=:all: erzwingt das getestete Wheel und vermeidet Build-Backend-Ausführung während dieses Bootstraps. |
| `AaGMS_8z7rRJBvbBA1nf` | `githubactions:S8541`, `.github/workflows/mock-campaign.yml:46` | valid_hardening; patch_prepared_pending_ci_and_rescan | Manuelle Mock-Kampagne: uv sync --locked konnte fremde Quellen bauen. --no-build untersagt diese Builds und bewahrt den explizit benötigten lokalen Editable-Build. Die frisch installierte Umgebung führte den vollständigen 96er-Mock-Katalog und den Archiv-Roundtrip erfolgreich aus. |
| `AaGMS_8z7rRJBvbBA1ng` | `githubactions:S8541`, `.github/workflows/mock-campaign.yml:49` | valid_hardening; patch_prepared_pending_ci_and_rescan | Manuelle Mock-Kampagne: uv run konnte trotz vorgelagertem Sync die Umgebung erneut abgleichen und dabei bauen. --no-sync --no-build verwendet ausschließlich die vorbereitete Umgebung. Der Kataloglauf mit diesen Flags lief vollständig ohne Modell-API-Aufruf. |
| `AaGMS_8z7rRJBvbBA1nh` | `githubactions:S7689`, `.github/workflows/mock-campaign.yml:88` | false_positive; corrected_review_no_remote_disposition | Korrektur vom 02.11.2026: S7689 verlangt bei Shell-Kommandosubstitution $() statt Backticks. Die gemeldeten Backticks sind hier Markdown-Zeichen innerhalb eines Python-Strings; der Schritt verwendet ausdrücklich shell: python {0}. Es findet an dieser Stelle keine Shell-Kommandosubstitution statt. Die frühere Erklärung zur Commit-Provenienz traf die Regelbedeutung nicht. git rev-parse HEAD bleibt eine unabhängig sinnvolle Provenienzangabe, ist aber kein Fix für S7689. Kontextueller False Positive; kein Sonar-Status wurde durch diese Nachprüfung geändert. |
| `AaGMS_8w7rRJBvbBA1nT` | `githubactions:S7689`, `.github/workflows/tests.yml:121` | false_positive; corrected_review_no_remote_disposition | Korrektur vom 02.11.2026: S7689 verlangt bei Shell-Kommandosubstitution $() statt Backticks. Die gemeldeten Backticks sind hier Markdown-Zeichen innerhalb eines Python-Strings; der Schritt verwendet ausdrücklich shell: python {0}. Es findet an dieser Stelle keine Shell-Kommandosubstitution statt. Die frühere Erklärung zur Commit-Provenienz traf die Regelbedeutung nicht. git rev-parse HEAD bleibt eine unabhängig sinnvolle Provenienzangabe, ist aber kein Fix für S7689. Kontextueller False Positive; kein Sonar-Status wurde durch diese Nachprüfung geändert. |
| `AaGMS_947rRJBvbBA1pV` | `python:S1192`, `scripts/ci_mock_campaign.py:79` | maintenance_debt; deferred_maintenance_debt | summary.json wird beim Erzeugen, Tabellenexport und späteren Lesen konsistent als derselbe feste Artefaktname verwendet. Die Wiederholung ist ein zutreffender Wartbarkeitshinweis, kein bestätigter Sicherheits- oder Laufzeitfehler. Konstantenextraktion bleibt offen; keine Scannerunterdrückung oder False-positive-Schließung. |
| `AaGMS_947rRJBvbBA1pW` | `python:S1192`, `scripts/ci_mock_campaign.py:84` | maintenance_debt; deferred_maintenance_debt | campaign.zip wird beim Export, Verifizieren und Wiederherstellen konsistent verwendet. Eine benannte Konstante könnte spätere Schreibfehler vermeiden; derzeit bestätigt der Roundtrip die Zuordnung. Diese berechtigte Wartbarkeitsschuld bleibt offen und wird nicht als behobener Fehler oder False positive ausgegeben. |
| `AaGMS_8w7rRJBvbBA1nP` | `githubactions:S8541`, `.github/workflows/tests.yml:43` | valid_hardening; patch_prepared_pending_ci_and_rescan | Offline-Python-Matrix: pip erhielt keine Vorgabe gegen Source-Builds des fest versionierten uv-Bootstraps. --only-binary=:all: schließt diesen Fallback. Die tatsächliche Installation von uv 0.12.23 mit diesem Flag war unter Linux erfolgreich; Windows wird in CI geprüft. |
| `AaGMS_8w7rRJBvbBA1nQ` | `githubactions:S8541`, `.github/workflows/tests.yml:44` | valid_hardening; patch_prepared_pending_ci_and_rescan | Offline-Python-Matrix: gesperrte Versionen allein verhindern keine fremden Build-Backends. uv sync --locked --no-build installiert Binärdistributionen der Abhängigkeiten und baut weiterhin das eigene Editable-Projekt. Frischer Sync ohne uv-Cache gelang; Lockdatei blieb unverändert. |
| `AaGMS_8w7rRJBvbBA1nU` | `githubactions:S6505`, `.github/workflows/tests.yml:142` | confirmed_install_hook_exposure; patch_prepared_pending_ci_and_rescan | Frontend-Matrix: npm ci erlaubte die Installations-Hooks der gesperrten Abhängigkeiten. --ignore-scripts unterbindet sie. Die unveränderte Lockdatei, 31 React-Tests und der Produktionsbuild funktionieren nach frischer Installation; keine zusätzliche Buildskript-Freigabe ist nötig. |
| `AaGMS_8w7rRJBvbBA1nV` | `githubactions:S8541`, `.github/workflows/tests.yml:167` | valid_hardening; patch_prepared_pending_ci_and_rescan | Backend-Installation im Frontend-Job: derselbe fest versionierte pip-Bootstrap erlaubte Source-Builds. Das ergänzte --only-binary=:all: verlangt ein kompatibles Wheel. Die Linux-CLI-Version und Flagkompatibilität wurden tatsächlich geprüft. |
| `AaGMS_8w7rRJBvbBA1nW` | `githubactions:S8541`, `.github/workflows/tests.yml:168` | valid_hardening; patch_prepared_pending_ci_and_rescan | Backend-Installation aus frontend/: --project .. ändert die Projektauflösung, aber --locked sperrt keine Buildskripte. Der ergänzte --no-build-Zwang funktioniert auch mit diesem relativen Projektpfad. Für spätere Playwright-Backendstarts gelten zusätzlich UV_NO_SYNC und UV_NO_BUILD. |
| `AaGMS_8w7rRJBvbBA1nX` | `githubactions:S6505`, `.github/workflows/tests.yml:170` | conditional_risk_hardened; patch_prepared_pending_ci_and_rescan | Frontend-Matrix: nach erfolgreichem npm ci ist die Playwright-CLI lokal und gesperrt; eine separate Installation wurde nicht beobachtet. Der generelle npx-Installationspfad samt Hooks wird durch node ./node_modules/@playwright/test/cli.js vollständig vermieden. |
| `AaGMS_8w7rRJBvbBA1nY` | `githubactions:S8543`, `.github/workflows/tests.yml:170` | conditional_risk_hardened; patch_prepared_pending_ci_and_rescan | Frontend-Matrix: die implizite npx-Auflösung wird durch einen festen Pfad zur ausdrücklich deklarierten, gesperrten Test-CLI ersetzt. Damit kann eine fehlende lokale CLI keine neue Paketversion aus dem Netz nachinstallieren. Die lokale Version 1.64.1 und Browserinstallationsoptionen wurden geprüft. |

## Tatsächlich ausgeführte Prüfungen und historische Grenzen

- **pip_binary_bootstrap — passed_linux**: Isolierte frische Python-3.12.14-Umgebung; pip install --only-binary=:all: uv==0.12.23 installierte das manylinux-Wheel erfolgreich. uv --version und lokale Hilfe bestätigen 0.12.23.
- **uv_wheel_dependency_sync — passed_linux**: uv 0.12.23 sync --locked --no-build --extra web --group dev --no-cache in neuer .venv: 21 Pakete installiert, nur das eigene Editable-Projekt gebaut; uv.lock unverändert.
- **npm_install_and_build — passed_linux**: Node 24.22.1/npm 11.9.0; npm ci --ignore-scripts mit neuem Cache: 122 Pakete. npm test: 31/31; npm run build: erfolgreich. Keine Hook-Ausnahme. package-lock.json unverändert; einziges hasInstallScript-Paket ist optionales macOS-fsevents.
- **playwright_cli_resolution — cli_passed_browser_pending**: node ./node_modules/@playwright/test/cli.js --version: 1.64.1; install --help und install --dry-run chromium erfolgreich. --dry-run --with-deps scheiterte an fehlenden apt-Paketindizes. Tatsächlicher Chromium-Download lieferte ein ungültiges ZIP und anschließend einen Lockfehler; kein Browserlauf erfolgreich behauptet. Linux-/Windows-GitHub-CI steht aus.
- **uv_project_path_and_runtime_flags — passed_linux**: Sync mit --project .. aus frontend/ erfolgreich; security-lab-web --help und FastAPI/Uvicorn-Imports mit UV_NO_SYNC=true/UV_NO_BUILD=true und uv 0.12.23 erfolgreich.
- **mock_catalog — passed_linux**: 96/96 synthetische Mock-Läufe vollständig und gültig; Archivintegrität/-vollständigkeit und Wiederherstellung geprüft; keine Modell-API-Aufrufe.
- **s7689_rule_and_python_shell_review — source_reviewed_2026_11_02**: Offizielle Regelbedeutung und beide Python-Schritte geprüft; False-Positive-Einordnung, keine Remote-Disposition.
- **summary_provenance — passed_linux**: Beide tatsächlichen Python-Zusammenfassungsblöcke ausgeführt; GITHUB_SHA absichtlich abweichend gesetzt. Ausgabe enthielt git rev-parse HEAD, nicht die Testvariable.
- **workflow_structure — passed**: Alle drei YAML-Dateien geparst; eingebettete Python-Blöcke kompiliert; git diff --check erfolgreich. Action-Referenzen unverändert.

## Grenzen des ursprünglichen Prüfstands vom 1. November 2026

- Keine Aussage über eine tatsächlich kompromittierte Abhängigkeit.
- Keine neue Modell-, Tool- oder Bewertungssemantik; keine realen Modellaufrufe.
- Lokaler Editable-Build und bewusst gestartete Projektwerkzeuge führen weiterhin Code aus; die Änderung ist keine vollständige Build-Sandbox.
- Windows und tatsächliche Browserintegration am endgültigen CI-Head stehen aus.
- Zwei S1192-Wartbarkeitshinweise bleiben offen; keine globale Unterdrückung.

## Primärquellen

- [uv CLI: --no-build, --locked, --no-sync](https://docs.astral.sh/uv/reference/cli/): Fremde Sdist-Builds ablehnen; eigener Editable-Build bleibt zulässig. Verhalten zusätzlich mit exakt uv 0.12.23 geprüft.
- [pip install: --only-binary](https://pip.pypa.io/en/stable/cli/pip_install/#cmdoption-only-binary): Binärdistributionen erzwingen statt Source-Fallback.
- [npm ci: --ignore-scripts](https://docs.npmjs.com/cli/v11/commands/npm-ci/#ignore-scripts): Abhängigkeits-Hooks abschalten; ausdrücklich aufgerufene Projektskripte bleiben ausführbar.
- [npm exec / npx](https://docs.npmjs.com/cli/v11/commands/npm-exec/#description): Lokale Auflösung und Paketinstallations-Fallback unterscheiden.
- [GitHub Actions variables](https://docs.github.com/en/actions/reference/workflows-and-actions/variables): GITHUB_SHA ist ereignisabhängig; tatsächlichen Checkout separat bestimmen.
- [Sonar staff: supply-chain rules](https://community.sonarsource.com/t/rules-to-reduce-supply-chain-risks/182615): Bestätigung der Regeln gegen ungesperrte Installationen und Build-/Installationsskripte. Nicht die Quelle für die nachträgliche S7689-Korrektur.
- [SonarQube Server 2026.1 LTA release notes: Shell / bash, S7689](https://docs.sonarsource.com/sonarqube-server/2026.1/server-update-and-maintenance/lta-to-lta-release-notes): Regelbedeutung für die datierte Korrektur der beiden S7689-Bewertungen.

## Beitrag

Im ursprünglichen Prüfstand vom 01.11.2026 prüfte ChatGPT/Codex diese 19 Befunde einzeln, härtete die drei CI-Workflows und führte die oben bezeichneten Linux-Prüfungen aus. Eine neue unabhängige Gegenprüfung des endgültigen integrierten Patches und die CI standen zu diesem Prüfzeitpunkt noch aus; menschliche Autorenabnahme wurde nicht behauptet.

Am 02.11.2026 ergänzte ChatGPT/Codex die quellengestützte Korrektur zu S7689. Die ursprünglichen Prüfprotokolle und IDs bleiben nachvollziehbar; eine menschliche Autorenabnahme oder Sonar-Statusänderung wird damit nicht behauptet.
