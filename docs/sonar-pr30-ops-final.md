# Separate final-three Sonar PR30 operations candidate

This candidate targets exactly three individually reviewed annotations at
`90667b5259fe2694734755f74cb56009be478b4b`. See REVIEW.md and triage-review.json.
It is outside the application checkout. No remote actions were performed by its
implementation agent. It defaults to read-only. Apply is blocked by an empty
APPROVED_ALLOWLIST_SHA256, approved=false and null expected_analysis_date.
The rule IDs come from the supplied current inventory; no disposition is inferred
from remote recommendations.

Use the existing isolated branch from main: `ops/sonar-pr30-triage`. Replace only:

1. .github/workflows/sonar-inventory.yml (existing dispatch entry, branch override).
2. scripts/sonar_pr30_triage.py.
3. scripts/sonar_pr30_allowlist.json.
4. tests/test_sonar_pr30_triage.py.

Do not merge this operations branch or deploy application code from it. The
workflow and runner both require the exact repository, owner/actor sxba-04,
workflow_dispatch event, and fixed operations branch. First dispatch apply=false.
Its sanitized receipt is quality-inventory/sonar-pr30-triage-final.json.
All nine prior CLI IDs and the real S5778 test finding are excluded from writes.

The safe transport and mutation logic is unchanged from the independently reviewed
nine-issue runner: fixed https://sonarcloud.io host/project/PR, redirects rejected,
no secret/raw message output, exact-token redaction, bounded pages/response/time,
no automatic retries, only concrete comment and falsepositive POSTs. Existing TLS
and proxy defaults remain intact. Receipt is exclusively reserved before transport.
All identities/rules/available transitions must match before any write; each issue
is refreshed before its comment and transition, followed by independent status
verification. Final selected set/status/identity and analysis date are checked.
Modern and legacy statuses must agree. Already false-positive issues are skipped.

After root reviews the fresh read-only receipt, match all three IDs/components/
rules/transitions and source evidence, set the exact analysis date, explicitly
approve the static allowlist, and pin its exact SHA256 in the runner. Commit the
reviewed files on the operations branch. Only a separate apply=true dispatch can
then write. No automatic approval/promotion helper exists.

POST permissions and Cloud behavior remain unverified for this new candidate.
Failure stops with sanitized partial state; it does not widen permissions, change
gates/rules, automatically replay a request or undo previous successful edits.
Read back partial outcomes before retrying. A comment-only interruption can leave
a duplicate evidence comment on a later manually approved retry.

Offline runner validation (separate from static application triage):

```
python -B -m unittest discover -s tests -p test_sonar_pr30_triage.py -v
```

All 23 operation-boundary tests pass with real network transport blocked. Tests
cover the exact three IDs, exclusion of the prior batch and S5778, unapproved pins,
comment-before-transition, final-status consistency, read-only defaults, token
redaction, scope/branch guards, pagination drift, time/size/redirect bounds and
existing receipt preservation. No new application tests or model calls were run.

API contract is the same as the earlier reviewed runner:
https://github.com/SonarSource/sonarqube/blob/master/sonar-ws/src/main/java/org/sonarqube/ws/client/issues/IssuesService.java
and SearchRequest.java in the same directory; add_comment uses issue/text and
 do_transition uses issue/transition as form-encoded POST parameters. Actual API
responses must satisfy the runner guards; source documentation is not proof of a
successful remote operation.
