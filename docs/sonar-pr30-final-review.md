# Independent static review: final three PR30 annotations

Reviewed source: `90667b5259fe2694734755f74cb56009be478b4b`. Source inventory: `/tmp/sonar-pr30-90667b5.json`; annotation locations: `/tmp/sonar-pr30-third-annotations.json`. The inventory reports analysis `2026-11-06T09:37:16+0000` but explicitly does not certify the Git revision. This review inspected source at the supplied annotation revision. No new application execution, security audit or live login is claimed.

Root SECURITY.md and docs/threat-model.md apply to all affected paths; no nested security policy exists. The assessment covers each exact claim, not blanket permission for redirects, tabindex or skipped tests.

| ID | Rule | Verdict |
|---|---|---|
| `AaGwHn_y3f6_aqzNEjB3` | `tssecurity:S6105` | not_actionable / individual false positive |
| `AaGwOUR7RVlkm00GzpSU` | `typescript:S6845` | not_actionable / individual false positive |
| `AaGwHoAJ3f6_aqzNEjCE` | `typescript:S1607` | not_actionable / individual false positive |

## 1. AaGwHn_y3f6_aqzNEjB3

Individual false-positive disposition for Sonar issue AaGwHn_y3f6_aqzNEjB3, rule tssecurity:S6105, project sxba-04_llm-agent-security-lab, PR30. Statically reviewed source revision: 90667b5259fe2694734755f74cb56009be478b4b. authorizationTarget in frontend/src/github-auth.ts:27-44 parses the API URL, rejects any origin other than https://github.com or path other than /login/oauth/authorize, rejects userinfo/fragments and duplicate query keys, and binds state, PKCE S256/challenge, redirect_uri and expiry to this browser login. It then constructs a fresh URL from the constant https://github.com/login/oauth/authorize and assigns only its search property; query text cannot replace protocol, host or path. startGitHubLogin returns only that result; AccessGate:47 awaits it before location.assign, and failures prevent navigation. The upstream JSON flow is reachable but does not establish an arbitrary redirect. No other shipped caller bypasses this helper. This disposition does not approve arbitrary API redirects or future changes to the helper. Detailed evidence: docs/sonar-triage/pr30-frontend.md and the final three-item static review. No rule, quality-gate or test-scope change is requested.

Primary reference: https://developer.mozilla.org/en-US/docs/Web/API/URL/search

## 2. AaGwOUR7RVlkm00GzpSU

Individual false-positive disposition for Sonar issue AaGwOUR7RVlkm00GzpSU, rule typescript:S6845, project sxba-04_llm-agent-security-lab, PR30. Statically reviewed source revision: 90667b5259fe2694734755f74cb56009be478b4b. ScrollRegion in frontend/src/ui.tsx:45-50 renders a named section with tabIndex=0. Every shipped use supplies table-scroll, code-block, text-block or source-text CSS; these have overflow:auto and constrained width/height. Keyboard focus is required to operate these scroll containers consistently across supported browsers, including evidence without focusable descendants. styles.css provides a visible focus outline; aria-label names the native region and no positive tab order is introduced. MDN overflow accessibility guidance explicitly recommends tabindex=0 and a named region for keyboard scrolling. Removing this focus target would reduce accessibility; the generic noninteractive-element rule misses this concrete scroll interaction. This disposition does not approve tabIndex on arbitrary static containers. Detailed evidence: docs/sonar-triage/pr30-frontend.md and the final three-item static review. No rule, quality-gate or test-scope change is requested.

Primary reference: https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/overflow#accessibility

## 3. AaGwHoAJ3f6_aqzNEjCE

Individual false-positive disposition for Sonar issue AaGwHoAJ3f6_aqzNEjCE, rule typescript:S1607, project sxba-04_llm-agent-security-lab, PR30. Statically reviewed source revision: 90667b5259fe2694734755f74cb56009be478b4b. frontend/e2e/visual.spec.ts:3-7 explicitly documents Linux-only baseline font/rendering differences and supplies the runtime skip reason Reviewed baseline is for Linux Chromium only. The condition skips only when process.platform is not linux. frontend/playwright.config.ts includes visual.spec.ts in Chromium and limits Firefox/WebKit projects to smoke specs. .github/workflows/tests.yml runs the complete Playwright suite on Linux and Chromium functional tests on Windows. Thus both light/dark screenshot assertions remain executed on the platform for which checked-in baselines exist; the test is neither globally disabled nor unexplained. Playwright visual-comparison documentation requires matching the baseline environment. This disposition does not exempt unexplained skips or claim Windows screenshot coverage. Detailed evidence: docs/sonar-triage/pr30-frontend.md and the final three-item static review. No rule, quality-gate or test-scope change is requested.

Primary reference: https://playwright.dev/docs/test-snapshots

The separate maintainability issue `AaGwHoBS3f6_aqzNEjCX` (`python:S5778`) is excluded; root is fixing its exception-test structure. All nine previous CLI issue IDs are excluded from this new fixed set.

The triage reference package exposed its result contract but two optional shared guidance resources could not be loaded. The complete main triage instructions, root security policy, concrete call graph, CI selection, CSS and primary platform documentation were inspected directly. No missing material product boundary remains for these three verdicts.
