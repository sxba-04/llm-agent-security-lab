# Security policy and review context

## System and scope

This repository is a synthetic research laboratory for indirect prompt injection in tool-using LLM applications. The ordinary FastAPI/React launcher binds to `127.0.0.1`. An explicitly selected hosted mode supports the two trusted operators through a GitHub Pages frontend and a separate HTTPS Python service. It authenticates high-entropy operator tokens but does not provide tenant isolation, reviewer identity enforcement or a general public registration system. See [hosting requirements](docs/hosting.md).

The execution core exposes only `read_ticket` and `append_note` against fresh in-memory synthetic tickets. The GUI starts mock campaigns only. A separate CLI adapter can contact a fixed model-provider endpoint after explicit paid-run configuration and operator acknowledgement.

Review the execution core, provider and budget handling, local HTTP service, PDF subprocess, campaign storage, review workflow, archive import/export, frontend rendering, dependencies and CI. Important assets are host files and credentials, campaign and review evidence, the study budget and the validity of experimental comparisons. See [the concrete threat model](docs/threat-model.md) and [experiment design](docs/experiment.md).

## Threat model and trust boundaries

- Legitimate task definitions and session permissions come from trusted, validated case fixtures.
- External article/PDF contents, model replies and tool arguments are untrusted. Their content must not acquire application authority.
- A malicious website may target the running loopback service. Host/Origin checks and mutation tokens must remain effective; loopback binding is not a reason to ignore browser-origin attacks.
- Imported PDF/ZIP bytes, filenames and stored evidence may be malformed or modified. Paths and resource use must be validated before they affect the host or reported results.
- The browser displays results and requests actions; it does not decide ticket permissions or scientific verdicts.
- Operators and their local workspace are not isolated tenants. Access to the same operating-system account can expose local files; the application does not claim to protect secrets from a fully compromised host.

## Security invariants

1. Model-controlled data must not enable host commands, arbitrary filesystem/network access or additional model tools.
2. Every ticket effect passes through the shared gateway and syntax checks. In P/FP, authorization must use trusted session data before the effect occurs.
3. The web API must remain mock-only and use managed workspace paths. Local mode must retain loopback Host/Origin and mutation-token checks. Hosted mode must authenticate every data endpoint including downloads, require the configured public Host and exact allowed Origins, preserve mutation/body checks, and reject missing or invalid configuration. Only the minimal `/healthz` GET is public.
4. Untrusted article, model and evidence text must render as data, not executable HTML or script.
5. PDF extraction and archive handling must enforce their documented bounds, reject unsafe paths and retain original source provenance. Confirmation must refer to the actual extracted text used.
6. Model credentials must not enter persisted configuration, logs, PDF child-process environments or responses. Paid calls must retain explicit activation, reservation/accounting and request limits.
7. Cancellation, transient file conflicts and error recovery must not replay model/tool work or erase observed effects. Invalid/incomplete runs must not become successful defenses.
8. Original run records, event evidence, PDF sources, rating inputs and adjudication history must remain linked and verifiable. Reports must distinguish integrity, completeness and authenticity.
9. Independent ratings and adjudications must be validated through shared code. Missing, mismatched or undecidable judgments must not silently become negative results.
10. Infrastructure controls must remain effective in every experimental condition.

## Interpreting experimental behavior

B and F intentionally omit authorization P inside the synthetic ticket backend. An unauthorized synthetic read or write in those conditions may be the intended measured outcome. Likewise, a content filter can miss an injected instruction, and an authorized note can contain an incorrect statement.

Assess whether the implementation violates the declared condition or a surrounding containment/data-integrity boundary. Do not fix the baseline by silently enabling the protection being evaluated. Conversely, host access, credential exposure, a P/FP bypass, browser-origin abuse or corrupted evidence is not excused by the experiment.

Mock success does not establish real-model security, and a failed API/PDF operation does not establish a successful defense.

## Reportability and severity

Report a concrete source-to-impact path, attacker-controlled input, prerequisites, affected condition and evidence. Calibrate severity to the actual local deployment and reachable impact; distinguish an exposed browser/PDF/archive boundary from a scenario that already requires unrestricted host control.

Known limitations do not authorize suppressing new findings. There are no blanket exclusions for local-only code, mock mode, dependencies, generated code, imported files or test fixtures. A control described here is an invariant to verify, not proof that the implementation satisfies it.

## Known limitations and outstanding validation

- Hosted operation requires a real HTTPS reverse proxy, one process and one service instance. The owner explicitly selected a free ephemeral demo: local uploads, campaign records and ratings are lost when the service sleeps, restarts or redeploys. `LAB_STORAGE_MODE=ephemeral` declares this lifecycle through authenticated health metadata and a persistent UI warning; it neither weakens authentication nor deletes files itself. Important study evidence must be exported and kept outside the demo. Durable shared evidence storage requires a separately authorized persistent deployment. Browser access tokens stay in memory, never frontend build variables, URLs or local storage. Server configuration stores only token hashes. Host/Origin checks do not replace authentication or TLS.
- Hosted operators share the same workspace and privileges. Separate tokens allow revocation but do not prove who authored a scientific rating, enforce independent A/B review slots, or isolate operators from one another. They remain trusted collaborators.
- A deployment can interrupt active mock jobs. Existing interruption/evidence handling must remain intact; no automatic replay of model or tool work is permitted. If ephemeral storage is erased, even the interruption record is unavailable; absence of evidence is not a successful experiment. Provider snapshots, where available, do not replace downloaded, verified campaign archives.

- The Python environment, CLI acknowledgement flag and PDF subprocess do not establish outer OS/container isolation. That setup remains to be independently verified before real-model experiments.
- PDF extraction has input/page/text/time limits. POSIX additionally applies CPU/address-space limits; Windows currently has no equivalent hard process-memory limit. This is a limitation, not a general sandbox claim.
- Archive hashes establish internal consistency, not authorship or authenticity against an actor who can replace evidence and its index together. Code at the recorded commit must be preserved separately from campaign archives.
- Campaign-list caching uses file metadata as a change detector. It is not an integrity proof or complete TOCTOU defense; opening evidence must still perform its full checks.
- The local API budget ledger is a safeguard based on configured estimates, not a provider invoice cap or a global ledger shared automatically across computers.
- The workbench supports separated rating views, not an access-control boundary against an operator who can read the same underlying files.

Changes to deployment exposure, supported tools, live-model activation or accepted risk require an explicit project decision and corresponding documentation.
