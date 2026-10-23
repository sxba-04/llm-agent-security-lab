# Project rules

- This is a synthetic research lab for an approved student project. Never connect tools to real tickets, mail, arbitrary URLs, shell commands, or production data.
- Python 3.12+; source in src/security_lab. Runtime should use the standard library unless a dependency has a clear benefit.
- B/F/P/FP are configurations of one code path. Syntax checks, prompts, tool schemas and outer containment stay identical.
- Session rights come from trusted case fixtures, never model output or article text. All tool effects go through one gateway.
- Log proposals before filtering; distinguish executed access, model-context exposure, and user-visible exposure. Evaluate independently of policy decisions.
- Mock runs are engineering checks, never empirical LLM findings. Keep development and final evaluation cases separate. Do not tune on final tests.
- No live API calls in CI or during development without configured credentials and an explicit paid-run command. The total project budget ceiling is EUR 250; no automatic paid experiments.
- Store no credentials in Git or logs. Do not disable TLS verification or organizational security controls.
- Document AI-generated contributions honestly; do not attribute unreviewed generated code to either student as original work.
- Use branches and reviewable commits; do not force-push shared history. Tests must cover real behavioral risks.
- Wait for required CI jobs and requested reviews to finish on the current PR head before merging. Address and recheck every finding; green tests alone are not review approval.
- The local workbench uses FastAPI and React by explicit team decision. Serve on loopback only; UI runs stay mock-only until a separate API-pilot decision.
- PDF import is a pre-experiment text extraction step. Preserve originals, extractor version and content hashes, require preview confirmation, and keep identical selected text across conditions.
- UI, CLI and reports must share the existing execution and evaluation modules. Never duplicate policy or semantic verdict logic in the frontend.
