# Repository context for Copilot

Read [AGENTS.md](../AGENTS.md), [SECURITY.md](../SECURITY.md) and the
[threat model](../docs/threat-model.md) before changing or reviewing code.
They are the shared project instructions; do not invent a separate review policy.

- This is a synthetic research lab. B/F/P/FP compare one execution path with
  deliberately different interventions. Do not silently add authorization to B/F
  or change the evaluator to make a defense appear successful.
- Keep outer containment, hosted authentication, PDF/archive bounds, evidence
  integrity and mock-only UI behavior effective in every condition.
- Keep model credentials out of code, logs, artifacts and browser builds. Tests
  must not call paid models; hosting changes must not create charges.
- Report concrete reachable defects with file/line evidence. Separate scanner
  findings, test results, scientific judgments and unavailable reviews.
- Follow the locked test commands and current-head review requirements in
  AGENTS.md. Never claim human approval or successful checks that did not occur.
