# One-off Sonar PR 30 operations branch

Prepared for root review only. No remote actions were performed while creating
these files. They are outside the application checkout. The first supported
operation is read-only. Apply is deliberately disabled: rules are null,
`approved` is false, and `APPROVED_ALLOWLIST_SHA256` is empty.

## Fixed scope

- Host: `https://sonarcloud.io`; project: `sxba-04_llm-agent-security-lab`; PR: 30.
- Exactly nine reviewed IDs: five backup/archive, two study, one scanner receipt,
  and one doctor. The OAuth redirect issue is excluded; it receives a code fix.
- Only issue comment and `falsepositive` transition POSTs are implemented.
  No rule, quality-gate, permission, billing or application-deployment changes.
- The runner requires repository/owner/actor `sxba-04`, exact repository
  `sxba-04/llm-agent-security-lab`, branch `ops/sonar-pr30-triage`, and event
  `workflow_dispatch`. These checks also exist in the workflow job guard.
- 500 issues maximum, 100 per page, 4 MiB per response, 20-second transport
  timeout, 240-second process alarm and eight-minute workflow timeout. No retries.
- Default proxy and TLS verification behavior is retained. Redirects are rejected.
  Requests use only fixed endpoints. Token, proxy values, raw bodies, messages,
  comments and source text are never emitted. Exact token echoes are redacted
  from the final JSON even in otherwise allowed identifier fields.

## Read-only publication

Create a separate branch from the current **main**, not from the feature branch:
`ops/sonar-pr30-triage`. Copy only the paths below into that branch:

1. `.github/workflows/sonar-inventory.yml` (replaces that existing dispatch workflow
   on this operations branch only).
2. `scripts/sonar_pr30_triage.py`.
3. `scripts/sonar_pr30_allowlist.json`.
4. `tests/test_sonar_pr30_triage.py`.

This README can be kept as the review receipt outside the application repository.
Do not merge this branch into main. Do not change the application deployment
branch or trigger Pages/Render. Use the existing workflow-dispatch entry with
ref `ops/sonar-pr30-triage` and input `apply=false`.

The workflow runs only the offline tests without credentials, then supplies the
existing `SONAR_TOKEN` solely to the runner. It uploads the sanitized receipt
even after a handled failure. Existing output is never overwritten: a receipt
is exclusively reserved before any remote request. CI provides a fresh checkout
for each dispatch; a locally retained receipt must be preserved separately.

Read-only output contains the exact PR issue IDs, rule IDs, components, available
transitions and bounded source-location coordinates, with analysisDate checked
before/after retrieval. It does not certify a Git revision; the report explicitly
sets `revision_verified_by_server=false`. Match analysis/run evidence separately.
Unknown server schemas, absent PR, oversized responses and pagination drift fail
closed instead of inventing a usable inventory.

## Later explicit apply preparation

After reviewing the returned inventory and the per-ID source evidence, root must
manually complete each of the nine static `rule` fields. Do not infer a disposition
from a remote title, rule recommendation or severity. Reconfirm the comments and
the code revision they describe. Copy the reviewed inventory's exact analysisDate
to `expected_analysis_date`, set `approved=true`, calculate the JSON file's SHA256,
and set that exact value in `APPROVED_ALLOWLIST_SHA256`. Commit those reviewed
changes only on the operations branch. There is no automatic promotion helper.

Only then dispatch `apply=true`. Before the first POST all nine IDs must still
exist in PR 30 and match their pinned rules/components. Each issue is re-read;
the runner posts its specific evidence comment, checks that the analysis did not
change, posts `transition=falsepositive`, and independently re-fetches status.
The final fetch must contain all nine, with matching identities and consistent
false-positive status. Existing false positives are skipped without another
comment. Modern and deprecated status fields must not contradict each other.

No batch atomicity is claimed. A transport error after a POST may leave a comment
or transition applied even if its response was lost. The receipt records
`comment_attempted`, `comment_confirmed`, `transition_attempted` or
`false_positive_verified`. Stop and inspect through a fresh read-only run before
retrying. A retry after a comment-only interruption can add another evidence
comment; it never automatically replays within the failed run. A status transition
already confirmed false positive is idempotently skipped on a later reviewed run.
Do not undo successful earlier dispositions merely because a later issue failed.

The existing token may lack Administer Issues permission. HTTP 401/403 causes a
sanitized failure; no token creation, permission widening or alternate host is
attempted. No raw server error is printed. Actual Cloud API compatibility and
permissions are intentionally determined by the read-only operation first.

## API contract checked against primary sources

- [SonarSource IssuesService.java](https://github.com/SonarSource/sonarqube/blob/master/sonar-ws/src/main/java/org/sonarqube/ws/client/issues/IssuesService.java):
  `POST api/issues/add_comment` takes `issue` and `text`;
  `POST api/issues/do_transition` takes `issue` and `transition`.
- [SonarSource SearchRequest.java](https://github.com/SonarSource/sonarqube/blob/master/sonar-ws/src/main/java/org/sonarqube/ws/client/issues/SearchRequest.java):
  `issues/search` supports `additionalFields=transitions` alongside issue and
  component filters. The request also explicitly scopes `pullRequest=30`.
- [Sonar Web API authentication and POST encoding](https://docs.sonarsource.com/sonarqube-server/extension-guide/web-api):
  bearer authentication and `application/x-www-form-urlencoded` POST bodies.

These primary API definitions are not a claim that the Cloud call succeeded.
Unsupported/deprecated response behavior fails closed and must be reviewed.

## Offline validation

From this directory, with Python 3.12:

```text
python -B -m unittest discover -s tests -p test_sonar_pr30_triage.py -v
```

Tests block real transport and cover read-only defaults, the exact nine IDs,
wrong project/PR/rule/component, missing issues, analysis drift, missing transition
permissions, comment-before-transition, partial failures, status verification,
idempotence, final-set drift, redirect/size limits, token-safe output, duplicate
JSON, branch/actor guards and existing receipt preservation. No model calls.
