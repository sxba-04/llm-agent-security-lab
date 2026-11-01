# Sonar: server, hosting, document and storage findings

Review date: 2026-11-01. Imported analysis revision: `12db393`; inspected source revision: `3731bcd9a86fd98aca9c8168c9b1bf8065b44d62`.

**All 66 assigned keys assessed exactly once: 15 contextual false positives, 2 reviewed intended uses, 49 valid maintainability debts, 0 newly confirmed defects attributable to these keys.** No remote Sonar issue was modified. A separate malformed-token error-path bug found during the review is fixed in the supplied patch.

`reviewed_intended_use` distinguishes real reported constructs used appropriately in context: the explicit hosted 0.0.0.0 binding and seeded non-cryptographic experiment shuffle. Their expressions are present; neither is represented as absent or a scanner parsing error.

The public SonarSource analyzer repository supplied the official rule descriptions linked per issue. For `pythonsecurity:S8707`, the public file returned 404: its exact title/prose remains unverified. Those ten findings are assessed from their actual positional flows and concrete CLI/managed-path trust boundaries, not an invented diagnostic message.

The archive final-copy failure-atomicity defect and explicit TLS-minimum hardening are already assigned to root. The contextual path/cleartext dispositions below do not dismiss the archive bug or duplicate those patches.

## Validation and fix

- 47 local tests passed: 18 server, 12 hosted, 10 jobs and 7 documents.
- 55 local archive/batch/review-integrity tests passed, including a new regression proving strict UTF-8 decoding is necessary even when all archive hashes have been recomputed.
- Actual browser fixture TLS context rejected TLS 1.0/TLS 1.1 and completed verified TLS 1.2/TLS 1.3 handshakes using MemoryBIO, without contacting an external service.
- A regex probe confirmed that replacing the ASCII port digit range with Unicode `\d` changes accepted input.
- Ledger keys, rules, source paths and lines match the 66-item assignment exactly; `git diff --check` passed for both patches.

These are Linux/Python 3.12.14 local results, not claims of merged CI or Windows results. No model API calls, cost-bearing resources, rule suppressions or remote dispositions were used.

**Additional confirmed bug:** local middleware compared an untrusted decoded header with `secrets.compare_digest(str,str)`. Non-ASCII header bytes caused `TypeError`/HTTP 500. The regression failed on both test values before the fix. Comparing UTF-8 supplied bytes with the generated ASCII session-token bytes now returns 403 and creates no campaign. This is malformed-input handling, not an authentication bypass and not a hosted-token defect.

Additional changes: one-line malformed-token correction with a negative test, and a strict UTF-8 archive regression test.

## Individual findings

| Issue | Rule | Source | Assessment |
|---|---|---|---|
| `AaGMS_8t7rRJBvbBA1nN` | `python:S1186` | `frontend/e2e-hosted/server.py:28` | valid_maintainability_debt |
| `AaGMS_8t7rRJBvbBA1nO` | `python:S5332` | `frontend/e2e-hosted/server.py:78` | false_positive |
| `AaGMS_9j7rRJBvbBA1o2` | `python:S1192` | `src/security_lab/archives.py:32` | valid_maintainability_debt |
| `AaGMS_9j7rRJBvbBA1o-` | `pythonsecurity:S8707` | `src/security_lab/archives.py:60` | false_positive |
| `AaGMS_9j7rRJBvbBA1o4` | `python:S3776` | `src/security_lab/archives.py:66` | valid_maintainability_debt |
| `AaGMS_9j7rRJBvbBA1o3` | `python:S1192` | `src/security_lab/archives.py:72` | valid_maintainability_debt |
| `AaGMS_9j7rRJBvbBA1o5` | `python:S3776` | `src/security_lab/archives.py:116` | valid_maintainability_debt |
| `AaGMS_9j7rRJBvbBA1o6` | `python:S5713` | `src/security_lab/archives.py:140` | valid_maintainability_debt |
| `AaGMS_9j7rRJBvbBA1o7` | `python:S3776` | `src/security_lab/archives.py:261` | valid_maintainability_debt |
| `AaGMS_9j7rRJBvbBA1o8` | `python:S3776` | `src/security_lab/archives.py:326` | valid_maintainability_debt |
| `AaGMS_9j7rRJBvbBA1o1` | `python:S1192` | `src/security_lab/archives.py:379` | valid_maintainability_debt |
| `AaGMS_9j7rRJBvbBA1o_` | `pythonsecurity:S8707` | `src/security_lab/archives.py:395` | false_positive |
| `AaGMS_9j7rRJBvbBA1o9` | `pythonsecurity:S8707` | `src/security_lab/archives.py:428` | false_positive |
| `AaGMS_9U7rRJBvbBA1oi` | `pythonsecurity:S8707` | `src/security_lab/batch.py:45` | false_positive |
| `AaGMS_9U7rRJBvbBA1oc` | `pythonsecurity:S8707` | `src/security_lab/batch.py:85` | false_positive |
| `AaGMS_9U7rRJBvbBA1oX` | `python:S2245` | `src/security_lab/batch.py:129` | reviewed_intended_use |
| `AaGMS_9U7rRJBvbBA1oY` | `python:S3776` | `src/security_lab/batch.py:134` | valid_maintainability_debt |
| `AaGMS_9U7rRJBvbBA1oh` | `pythonsecurity:S8707` | `src/security_lab/batch.py:155` | false_positive |
| `AaGMS_9U7rRJBvbBA1oW` | `python:S1192` | `src/security_lab/batch.py:164` | valid_maintainability_debt |
| `AaGMS_9U7rRJBvbBA1og` | `pythonsecurity:S8707` | `src/security_lab/batch.py:236` | false_positive |
| `AaGMS_9U7rRJBvbBA1oZ` | `python:S3776` | `src/security_lab/batch.py:262` | valid_maintainability_debt |
| `AaGMS_9U7rRJBvbBA1of` | `pythonsecurity:S8707` | `src/security_lab/batch.py:319` | false_positive |
| `AaGMS_9U7rRJBvbBA1od` | `pythonsecurity:S8707` | `src/security_lab/batch.py:320` | false_positive |
| `AaGMS_9U7rRJBvbBA1oa` | `python:S2201` | `src/security_lab/batch.py:328` | false_positive |
| `AaGMS_9U7rRJBvbBA1ob` | `python:S3776` | `src/security_lab/batch.py:336` | valid_maintainability_debt |
| `AaGMS_9U7rRJBvbBA1oe` | `pythonsecurity:S8707` | `src/security_lab/batch.py:388` | false_positive |
| `AaGMS_9H7rRJBvbBA1oM` | `python:S1192` | `src/security_lab/documents.py:140` | valid_maintainability_debt |
| `AaGMS_9H7rRJBvbBA1oL` | `python:S1192` | `src/security_lab/documents.py:144` | valid_maintainability_debt |
| `AaGMS_9H7rRJBvbBA1oO` | `python:S1192` | `src/security_lab/documents.py:150` | valid_maintainability_debt |
| `AaGMS_9H7rRJBvbBA1oP` | `python:S3776` | `src/security_lab/documents.py:158` | valid_maintainability_debt |
| `AaGMS_9H7rRJBvbBA1oN` | `python:S1192` | `src/security_lab/documents.py:160` | valid_maintainability_debt |
| `AaGMS_9F7rRJBvbBA1oJ` | `python:S6353` | `src/security_lab/hosted.py:28` | false_positive |
| `AaGMS_9F7rRJBvbBA1oK` | `python:S3776` | `src/security_lab/hosted.py:74` | valid_maintainability_debt |
| `AaGMS_9F7rRJBvbBA1oH` | `python:S1192` | `src/security_lab/hosted.py:85` | valid_maintainability_debt |
| `AaGMS_9F7rRJBvbBA1oI` | `python:S1192` | `src/security_lab/hosted.py:147` | valid_maintainability_debt |
| `AaGMS_857rRJBvbBA1n8` | `python:S8392` | `src/security_lab/hosted_cli.py:51` | reviewed_intended_use |
| `AaGMS_9b7rRJBvbBA1ol` | `python:S3776` | `src/security_lab/jobs.py:93` | valid_maintainability_debt |
| `AaGMS_9b7rRJBvbBA1ok` | `python:S1192` | `src/security_lab/jobs.py:103` | valid_maintainability_debt |
| `AaGMS_9b7rRJBvbBA1om` | `python:S3776` | `src/security_lab/jobs.py:258` | valid_maintainability_debt |
| `AaGMS_9b7rRJBvbBA1on` | `python:S7504` | `src/security_lab/jobs.py:340` | false_positive |
| `AaGMS_837rRJBvbBA1nj` | `python:S3776` | `src/security_lab/server.py:45` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1nk` | `python:S5332` | `src/security_lab/server.py:51` | false_positive |
| `AaGMS_837rRJBvbBA1nl` | `python:S3776` | `src/security_lab/server.py:151` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1nt` | `python:S8415` | `src/security_lab/server.py:195` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1nu` | `python:S8415` | `src/security_lab/server.py:202` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1ni` | `python:S1192` | `src/security_lab/server.py:253` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1ny` | `python:S8415` | `src/security_lab/server.py:281` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1nz` | `python:S8415` | `src/security_lab/server.py:284` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1n0` | `python:S8415` | `src/security_lab/server.py:286` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1n3` | `python:S8415` | `src/security_lab/server.py:298` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1n2` | `python:S8415` | `src/security_lab/server.py:310` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1nm` | `python:S8415` | `src/security_lab/server.py:334` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1nn` | `python:S8415` | `src/security_lab/server.py:346` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1no` | `python:S8415` | `src/security_lab/server.py:349` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1np` | `python:S8415` | `src/security_lab/server.py:353` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1nq` | `python:S8415` | `src/security_lab/server.py:360` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1nr` | `python:S8415` | `src/security_lab/server.py:367` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1ns` | `python:S8415` | `src/security_lab/server.py:372` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1nv` | `python:S8415` | `src/security_lab/server.py:419` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1nw` | `python:S8415` | `src/security_lab/server.py:423` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1nx` | `python:S8415` | `src/security_lab/server.py:443` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1n1` | `python:S8415` | `src/security_lab/server.py:487` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1n4` | `python:S8415` | `src/security_lab/server.py:542` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1n5` | `python:S8415` | `src/security_lab/server.py:555` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1n6` | `python:S8415` | `src/security_lab/server.py:558` | valid_maintainability_debt |
| `AaGMS_837rRJBvbBA1n7` | `python:S8415` | `src/security_lab/server.py:563` | valid_maintainability_debt |

### AaGMS_8t7rRJBvbBA1nN

**valid_maintainability_debt** — `python:S1186` at `frontend/e2e-hosted/server.py:28`.

The empty override suppresses BaseHTTPRequestHandler console output in the synthetic HTTPS browser fixture. It is intentional, but the method has no nested explanation.

Controls / context: This override only changes access logging; serving and error responses are inherited. It is not the production application logger.

Validation: Source review; actual fixture SSLContext tested with verified in-memory TLS handshakes (no external service).

Official rule: [python:S1186](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S1186.html)

Action: Leave open as a small documentation debt; add an explanatory nested comment in a future fixture cleanup.

### AaGMS_8t7rRJBvbBA1nO

**false_positive** — `python:S5332` at `frontend/e2e-hosted/server.py:78`.

ThreadingHTTPServer.serve_forever is called only after its socket has been replaced by SSLContext(PROTOCOL_TLS_SERVER).wrap_socket(..., server_side=True). The reported server call actually serves HTTPS.

Controls / context: Fixture binds loopback and creates a synthetic certificate. Runtime is supported Python>=3.12. Current TLS context minimum is TLS 1.2; the combined correction also declares the minimum explicitly for the CodeQL alert.

Validation: Actual fixture configuration probed via SSL MemoryBIO: server rejects TLS 1.0/TLS 1.1 with UNSUPPORTED_PROTOCOL; verified TLS 1.2 and TLS 1.3 handshakes succeed.

Official rule: [python:S5332](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S5332.html)

Action: The combined correction includes the explicit TLS minimum. No remote Sonar disposition performed.

### AaGMS_9j7rRJBvbBA1o2

**valid_maintainability_debt** — `python:S1192` at `src/security_lab/archives.py:32`.

The same rejection message occurs in three _safe_name branches. This is valid duplication debt without an observed behavior defect.

Controls / context: Each branch rejects a distinct unsafe name category; message consolidation must retain all checks.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_archives.ArchiveTests.test_paths_links_duplicates_and_excessive_expansion_rejected

Source: Archive member name validation at archives.py:32,35,38

Sink / construct: archives.py:32 repeated error literal

Official rule: [python:S1192](https://github.com/SonarSource/sonar-python/blob/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S1192.html)

Action: Keep finding open for a scoped maintenance change.

### AaGMS_9j7rRJBvbBA1o-

**false_positive** — `pythonsecurity:S8707` at `src/security_lab/archives.py:60`.

verify-archive is explicitly a CLI operation on an operator-selected archive file. The outer file path is not derived from archive members.

Controls / context: _verify_into rejects symlink/non-file/oversized archive inputs before inspecting members. Members pass _safe_name, duplicate/case-collision, file type, compression, byte budget and integrity checks before isolated extraction. The hash read reports integrity of the already selected archive; there is no cross-user access boundary in the CLI.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_archives.ArchiveTests.test_paths_links_duplicates_and_excessive_expansion_rejected; tests.test_archives.ArchiveTests.test_roundtrip_preserves_evidence_reviews_and_original_zip; tests.test_archives.ArchiveTests.test_hash_tamper_rejected_and_import_destination_not_created

Source: cli.py:94 parse_args; cli.py:175 verify_archive(args.archive)

Sink / construct: archives.py:60 path.open("rb") in _sha, called from _verify_into at :313

Rule metadata limit: Official public analyzer rule file returned 404; classification uses actual imported positional flow and inspected trust boundary. Exact official title/prose is not claimed.

Action: Proposed individual false-positive disposition after parent review; no remote mutation performed.

### AaGMS_9j7rRJBvbBA1o4

**valid_maintainability_debt** — `python:S3776` at `src/security_lab/archives.py:66`.

_known_json_evidence recognizes several explicitly supported evidence schemas and path contexts. The number of distinct recognizers creates real cognitive load.

Controls / context: Unknown JSON is rejected rather than silently granted a trusted role. Future refactor can separate schema recognizers without weakening the reserved-path and verified-path checks.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_archives.ArchiveTests.test_unknown_json_cannot_silently_erase_review_role_but_opaque_non_json_is_preserved; tests.test_archives.ArchiveTests.test_legacy_summary_without_additive_paired_comparisons_remains_archivable; tests.test_archives.ArchiveTests.test_unindexed_uppercase_json_in_records_is_not_a_canonical_record

Source: Parsed supplementary JSON evidence and its campaign-relative path

Sink / construct: archives.py:66 _known_json_evidence

Official rule: [python:S3776](https://github.com/SonarSource/sonar-python/blob/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S3776.html)

Action: Keep finding open for a scoped maintenance change.

### AaGMS_9j7rRJBvbBA1o3

**valid_maintainability_debt** — `python:S1192` at `src/security_lab/archives.py:72`.

The manifest filename is repeated in evidence recognition and archive consistency verification. A shared constant could improve maintenance; current values are consistent.

Controls / context: Reserved file recognition and semantic checks intentionally refer to the canonical campaign manifest.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_archives.ArchiveTests.test_roundtrip_preserves_evidence_reviews_and_original_zip

Source: Fixed internal filename at archives.py:72, 127,217

Sink / construct: archives.py:72 manifest filename literal

Official rule: [python:S1192](https://github.com/SonarSource/sonar-python/blob/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S1192.html)

Action: Keep finding open for a scoped maintenance change.

### AaGMS_9j7rRJBvbBA1o5

**valid_maintainability_debt** — `python:S3776` at `src/security_lab/archives.py:116`.

_review_history_check discovers versions, binds their input mappings and CSVs, validates chain history and replays decisions. This is valid maintainability debt in an integrity-sensitive verifier.

Controls / context: Canonical input hashes and reproducible combination/adjudication replay validate claims even after self-hashes are recomputed. Do not remove predecessor checks or tolerate unknown review versions as a complexity fix.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_archives.ArchiveTests.test_adjudicated_review_roundtrip_validates_all_versions_and_preserves_originals; tests.test_archives.ArchiveTests.test_history_requires_predecessor_and_preserves_prior_ratings; tests.test_archives.ArchiveTests.test_review_inputs_and_per_judgment_mapping_are_bound_even_with_new_self_hash

Source: Archived review JSON, mappings, packets, rating CSVs and predecessor links

Sink / construct: archives.py:116 _review_history_check

Official rule: [python:S3776](https://github.com/SonarSource/sonar-python/blob/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S3776.html)

Action: Keep finding open for a scoped maintenance change.

### AaGMS_9j7rRJBvbBA1o6

**valid_maintainability_debt** — `python:S5713` at `src/security_lab/archives.py:140`.

UnicodeError is a subclass of ValueError. Catching both in the same except tuple is redundant but catches the intended errors; it is not evidence of a missing rejection.

Controls / context: The block raises a sanitized ValueError for unreadable campaign JSON. A small future cleanup may retain ValueError alone; runtime behavior remains the same.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_archives.ArchiveTests.test_corrupted_older_or_latest_combined_version_rejected_before_export; tests.test_archives.ArchiveTests.test_rehashed_zip_cannot_certify_malformed_review_version

Source: Malformed JSON/UTF-8 from supplementary campaign JSON

Sink / construct: archives.py:140 except (ValueError, UnicodeError)

Official rule: [python:S5713](https://github.com/SonarSource/sonar-python/blob/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S5713.html)

Action: Keep finding open for a scoped maintenance change.

### AaGMS_9j7rRJBvbBA1o7

**valid_maintainability_debt** — `python:S3776` at `src/security_lab/archives.py:261`.

_verify_into has multiple nested loops and checks for archive member types, names, collisions, size/expansion budgets, inventory integrity and semantic campaign verification. Its complexity is real.

Controls / context: Independent checks enforce containment, bounded resource use and evidence consistency. Refactoring should separate ZIP inventory validation from extraction and semantic checking while preserving every bound.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_archives.ArchiveTests.test_paths_links_duplicates_and_excessive_expansion_rejected; tests.test_archives.ArchiveTests.test_rehashed_extra_pdf_source_must_still_contain_valid_utf8; tests.test_archives.ArchiveTests.test_archive_manifest_inconsistency_is_rejected_even_with_matching_index

Source: Externally supplied ZIP and JSON index

Sink / construct: archives.py:261 _verify_into

Official rule: [python:S3776](https://github.com/SonarSource/sonar-python/blob/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S3776.html)

Action: Keep finding open for a scoped maintenance change.

### AaGMS_9j7rRJBvbBA1o8

**valid_maintainability_debt** — `python:S3776` at `src/security_lab/archives.py:326`.

export_campaign performs bounded source enumeration, integrity validation, mutation detection, ZIP assembly, verification and publication. These responsibilities justify a later carefully tested decomposition.

Controls / context: Symlink/special-file rejection, evidence validation and before/after source stat checks are intentional. Root separately addresses failed final publication atomically; avoid overlapping broad refactor.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_archives.ArchiveTests.test_roundtrip_preserves_evidence_reviews_and_original_zip; tests.test_archives.ArchiveTests.test_export_rejects_symlinks_and_inside_output; tests.test_archives.ArchiveTests.test_pdf_original_extraction_metadata_confirmation_and_missing_files_rejected

Source: Operator-selected campaign directory and archive destination

Sink / construct: archives.py:326 export_campaign

Official rule: [python:S3776](https://github.com/SonarSource/sonar-python/blob/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S3776.html)

Action: Keep finding open for a scoped maintenance change.

### AaGMS_9j7rRJBvbBA1o1

**valid_maintainability_debt** — `python:S1192` at `src/security_lab/archives.py:379`.

The source-mutation rejection text occurs at several export race checks. Repeated message spelling is a maintenance issue; the checks protect distinct points in the export operation.

Controls / context: No mutation check should be deleted when consolidating the message. Root atomic-publication work may shift these locations.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_archives.ArchiveTests.test_roundtrip_preserves_evidence_reviews_and_original_zip; tests.test_archives.ArchiveTests.test_export_rejects_symlinks_and_inside_output

Source: Source stat and inventory changes at archives.py:379,382,388,392

Sink / construct: archives.py:379 repeated error literal

Official rule: [python:S1192](https://github.com/SonarSource/sonar-python/blob/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S1192.html)

Action: Keep finding open for a scoped maintenance change.

### AaGMS_9j7rRJBvbBA1o_

**false_positive** — `pythonsecurity:S8707` at `src/security_lab/archives.py:395`.

The archive destination is chosen by the local operator in the archive command. No archive member, article, model response or request path chooses this outer destination.

Controls / context: Rejects an output inside the campaign and an existing or symlink output; exclusive final open prevents overwriting an existing file. Input campaign paths reject symlinks/special files; bounded ZIP contents are verified before final publication. Separate failure-atomicity defect in this baseline final copy is addressed by the combined atomic-publication correction; it does not make this operator-root taint path a traversal vulnerability.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_archives.ArchiveTests.test_roundtrip_preserves_evidence_reviews_and_original_zip; tests.test_archives.ArchiveTests.test_export_rejects_symlinks_and_inside_output

Source: cli.py:94 parse_args; cli.py:172 export_campaign(args.directory, args.output)

Sink / construct: archives.py:395 output_path.open("xb")

Rule metadata limit: Official public analyzer rule file returned 404; classification uses actual imported positional flow and inspected trust boundary. Exact official title/prose is not claimed.

Action: Proposed false-positive disposition for this path-taint trace only. Root separately fixes partial archive publication; do not use this decision to dismiss that distinct confirmed defect.

### AaGMS_9j7rRJBvbBA1o9

**false_positive** — `pythonsecurity:S8707` at `src/security_lab/archives.py:428`.

restore-archive deliberately creates the operator-selected destination; archive-controlled names are confined within a fresh sibling temporary directory before the final rename.

Controls / context: Destination must initially be absent and non-symlink; a second existence check precedes publication. Fresh mkdtemp directory receives only _verify_into-validated regular members; names cannot escape it. Original archive preservation is hash checked. A finally block removes failed temporary imports. Same-OS-user filesystem races are not a tenant-isolation promise.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_archives.ArchiveTests.test_roundtrip_preserves_evidence_reviews_and_original_zip; tests.test_archives.ArchiveTests.test_paths_links_duplicates_and_excessive_expansion_rejected; tests.test_archives.ArchiveTests.test_rehashed_extra_pdf_source_must_still_contain_valid_utf8; tests.test_archives.ArchiveTests.test_hash_tamper_rejected_and_import_destination_not_created

Source: cli.py:94 parse_args; cli.py:178 import_campaign(args.archive, args.output)

Sink / construct: archives.py:428 temporary.rename(destination)

Rule metadata limit: Official public analyzer rule file returned 404; classification uses actual imported positional flow and inspected trust boundary. Exact official title/prose is not claimed.

Action: Proposed individual false-positive disposition after parent review; no remote mutation performed.

### AaGMS_9U7rRJBvbBA1oi

**false_positive** — `pythonsecurity:S8707` at `src/security_lab/batch.py:45`.

The reported replace destination comes from the CLI freeze output argument. The operator intentionally chooses a snapshot path; imported data does not pick it.

Controls / context: CLI freeze checks for an existing snapshot before calling write_json. The generic writer uses an exclusive random temporary in the selected parent, fsync and bounded Windows sharing-violation retries, then atomic replacement. This path finding does not establish a hostile root or a privilege boundary. The generic replace writer is not a security sandbox.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_batch.BatchTests.test_json_writes_preserve_surrogates_and_reject_nonfinite; tests.test_batch.BatchTests.test_campaign_reset_hash_checks_and_no_overwrite

Source: cli.py:94 parse_args; cli.py:166 freeze args.output

Sink / construct: batch.py:45 tmp.replace(path)

Rule metadata limit: Official public analyzer rule file returned 404; classification uses actual imported positional flow and inspected trust boundary. Exact official title/prose is not claimed.

Action: Proposed individual false-positive disposition after parent review; no remote mutation performed.

### AaGMS_9U7rRJBvbBA1oc

**false_positive** — `pythonsecurity:S8707` at `src/security_lab/batch.py:85`.

The reported destination originates in the local operator CLI output argument, not archive/model content. Creating a new adjudication version at a selected filesystem path is intended CLI behavior.

Controls / context: write_json_new validates canonical JSON before publication; random same-directory temporary is opened exclusively and fsynced. Hard-link publication is create-if-absent: an existing destination is not replaced. Caller rejects existing versions and non-JSON extension. The OS account controls this output root; the threat model does not isolate the CLI from its own operator.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_review_integrity.ReviewIntegrityTests.test_cli_adjudication_does_not_overwrite_a_concurrently_created_version; tests.test_review_integrity.ReviewIntegrityTests.test_cli_adjudication_requires_json_extension_before_creating_output

Source: cli.py:94 parse_args; cli.py:160 review-adjudicate args.output

Sink / construct: batch.py:85 os.link(temporary, path)

Rule metadata limit: Official public analyzer rule file returned 404; classification uses actual imported positional flow and inspected trust boundary. Exact official title/prose is not claimed.

Action: Proposed individual false-positive disposition after parent review; no remote mutation performed.

### AaGMS_9U7rRJBvbBA1oX

**reviewed_intended_use** — `python:S2245` at `src/security_lab/batch.py:129`.

Seeded shuffling randomizes paired experiment execution order reproducibly. It does not generate an authentication token, secret, cryptographic key or authorization decision.

Controls / context: Condition lists, repetition range and seed type are validated. Separate fixture seeds and temporary filename randomness use secrets.token_hex rather than this experiment PRNG. Replacing this PRNG with nondeterministic secret randomness would defeat reproducible schedule validation.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_batch.BatchTests.test_paired_schedule_reproducible_complete; tests.test_batch.BatchTests.test_schedule_rejects_duplicate_conditions

Source: batch.py:122 random.Random(seed); seed is an explicit experiment parameter

Sink / construct: batch.py:129 rng.shuffle(block)

Official rule: [python:S2245](https://github.com/SonarSource/sonar-python/blob/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S2245.html)

Action: Retain the intended use and document the contextual review; no remote disposition performed.

### AaGMS_9U7rRJBvbBA1oY

**valid_maintainability_debt** — `python:S3776` at `src/security_lab/batch.py:134`.

run_batch combines preflight checks, scheduling, cancellation, model execution, immutable record publication, derived-event recovery, progress callbacks and final state persistence. The substantial nested control flow is real.

Controls / context: Tests cover cancellation before/during/after a run, provider factory failure, and preservation of canonical evidence on derived-event write failure. Any later extraction must preserve one-model-call semantics and the canonical-before-derived write ordering.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_batch.BatchTests.test_cancel_before_first_run_preserves_empty_campaign; tests.test_batch.BatchTests.test_cancel_current_run_preserves_partial_evidence; tests.test_batch.BatchTests.test_factory_exception_preserves_progress; tests.test_batch.BatchTests.test_failed_derived_event_write_preserves_canonical_evidence

Source: Batch execution inputs and cooperative cancellation callbacks

Sink / construct: batch.py:134 run_batch

Official rule: [python:S3776](https://github.com/SonarSource/sonar-python/blob/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S3776.html)

Action: Keep finding open for a scoped maintenance change.

### AaGMS_9U7rRJBvbBA1oh

**false_positive** — `pythonsecurity:S8707` at `src/security_lab/batch.py:155`.

A CLI run/demo campaign root is deliberately user-selectable. Forcing this path under a fixed repository root would remove supported CLI functionality without enforcing an applicable boundary.

Controls / context: Schedule and limits are validated before output creation. exist_ok=False rejects reuse of a pre-existing campaign root. Campaign-owned child paths are generated by the batch implementation; this reported source is the trusted operator root.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_batch.BatchTests.test_campaign_reset_hash_checks_and_no_overwrite; tests.test_batch.BatchTests.test_cancel_before_first_run_preserves_empty_campaign

Source: cli.py:94 parse_args; cli.py:105 run_batch args.output

Sink / construct: batch.py:155 output.mkdir(parents=True, exist_ok=False)

Rule metadata limit: Official public analyzer rule file returned 404; classification uses actual imported positional flow and inspected trust boundary. Exact official title/prose is not claimed.

Action: Proposed individual false-positive disposition after parent review; no remote mutation performed.

### AaGMS_9U7rRJBvbBA1oW

**valid_maintainability_debt** — `python:S1192` at `src/security_lab/batch.py:164`.

The fixed manifest filename is repeated in batch creation, progress updates and loading. Repetition is accurately detected and may drift when changed, but it currently names the same intended evidence file.

Controls / context: This literal is not user-controlled and does not itself introduce a path traversal.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_batch.BatchTests.test_campaign_reset_hash_checks_and_no_overwrite

Source: Fixed internal filename repeated at batch.py:164,169,206,225,344

Sink / construct: batch.py:164 manifest filename literal

Official rule: [python:S1192](https://github.com/SonarSource/sonar-python/blob/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S1192.html)

Action: Keep finding open for a scoped maintenance change.

### AaGMS_9U7rRJBvbBA1og

**false_positive** — `pythonsecurity:S8707` at `src/security_lab/batch.py:236`.

The supplied trace starts with the CLI review-export campaign directory. Reading that operator-selected campaign is intentional; untrusted child paths are checked independently.

Controls / context: _campaign_path rejects absolute paths, empty/dot/parent components, backslashes, colons, and symlink components. The resolved child must remain under the resolved campaign directory. This traced child is the fixed manifest filename. Manifest, cases, record hashes and event consistency are validated before accepting campaign evidence.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_batch.BatchTests.test_campaign_reset_hash_checks_and_no_overwrite; tests.test_archives.ArchiveTests.test_roundtrip_preserves_evidence_reviews_and_original_zip

Source: cli.py:94 parse_args; cli.py:142 load_results(args.directory)

Sink / construct: batch.py:236 path.read_text in _json_read; traced via manifest read at batch.py:344

Rule metadata limit: Official public analyzer rule file returned 404; classification uses actual imported positional flow and inspected trust boundary. Exact official title/prose is not claimed.

Action: Proposed individual false-positive disposition after parent review; no remote mutation performed.

### AaGMS_9U7rRJBvbBA1oZ

**valid_maintainability_debt** — `python:S3776` at `src/security_lab/batch.py:262`.

verify_document_sources combines case/provenance validation, run event binding, extra-source enumeration and file integrity checks. The complexity finding is valid; no required branch was found to be safely removable.

Controls / context: Path, hash, metadata, confirmation and strict UTF-8 checks enforce separate rejection conditions. Later helpers should retain validation of extra sources as well as referenced sources.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_archives.ArchiveTests.test_pdf_original_extraction_metadata_confirmation_and_missing_files_rejected; tests.test_archives.ArchiveTests.test_rehashed_extra_pdf_source_must_still_contain_valid_utf8; tests.test_archives.ArchiveTests.test_rehashed_zip_cannot_replace_original_pdf_or_remove_referenced_source

Source: Case snapshots, canonical run records and managed source evidence

Sink / construct: batch.py:262 verify_document_sources

Official rule: [python:S3776](https://github.com/SonarSource/sonar-python/blob/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S3776.html)

Action: Keep finding open for a scoped maintenance change.

### AaGMS_9U7rRJBvbBA1of

**false_positive** — `pythonsecurity:S8707` at `src/security_lab/batch.py:319`.

The tainted root is the operator-selected campaign directory, while imported PDF source identifiers and child names are constrained before reading the original PDF.

Controls / context: Referenced document IDs must match the restricted alphanumeric/underscore/hyphen grammar. _campaign_path performs component, symlink and resolved-containment checks on each source file. Any extra source must be a real non-symlink directory. Original bytes, extraction bytes and confirmation must match their recorded hashes.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_archives.ArchiveTests.test_pdf_original_extraction_metadata_confirmation_and_missing_files_rejected; tests.test_archives.ArchiveTests.test_rehashed_zip_cannot_replace_original_pdf_or_remove_referenced_source; tests.test_archives.ArchiveTests.test_export_rejects_symlinks_and_inside_output

Source: cli.py:94 and :142 args.directory; load_results -> verify_document_sources

Sink / construct: batch.py:319 original PDF Path.read_bytes()

Rule metadata limit: Official public analyzer rule file returned 404; classification uses actual imported positional flow and inspected trust boundary. Exact official title/prose is not claimed.

Action: Proposed individual false-positive disposition after parent review; no remote mutation performed.

### AaGMS_9U7rRJBvbBA1od

**false_positive** — `pythonsecurity:S8707` at `src/security_lab/batch.py:320`.

The extracted-text read is inside the selected campaign and passes the same child-path checks as original PDF evidence. The CLI root itself is intentionally unrestricted for its operator.

Controls / context: Referenced document ID grammar rejects path separators and traversal tokens. _campaign_path rejects malformed relative paths/symlinks and enforces resolved containment. Extraction hash and confirmation are checked, then strict UTF-8 validation rejects even a rehashed malformed extra source.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_archives.ArchiveTests.test_pdf_original_extraction_metadata_confirmation_and_missing_files_rejected; tests.test_archives.ArchiveTests.test_rehashed_extra_pdf_source_must_still_contain_valid_utf8; tests.test_archives.ArchiveTests.test_export_rejects_symlinks_and_inside_output

Source: cli.py:94 and :142 args.directory; load_results -> verify_document_sources

Sink / construct: batch.py:320 extracted text Path.read_bytes()

Rule metadata limit: Official public analyzer rule file returned 404; classification uses actual imported positional flow and inspected trust boundary. Exact official title/prose is not claimed.

Action: Proposed individual false-positive disposition after parent review; no remote mutation performed.

### AaGMS_9U7rRJBvbBA1oa

**false_positive** — `python:S2201` at `src/security_lab/batch.py:328`.

The decode call is a strict validation step: malformed extracted bytes must raise. Its return string is intentionally unused because original evidence bytes and their hashes are retained.

Controls / context: UnicodeDecodeError propagates from verify_document_sources; archive verification converts it to a rejected invalid/inconsistent archive. An extra unreferenced managed source can have self-consistent hashes yet invalid UTF-8; the new negative test proves removing this call would remove a necessary rejection. Sonar S2201 documentation itself recognizes exceptions as side effects, although its syntactic exception handling does not follow this propagation.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_archives.ArchiveTests.test_rehashed_extra_pdf_source_must_still_contain_valid_utf8; tests.test_archives.ArchiveTests.test_pdf_original_extraction_metadata_confirmation_and_missing_files_rejected

Source: batch.py:320 extracted bytes after path, metadata, hash and confirmation checks

Sink / construct: batch.py:328 extracted.decode("utf-8")

Official rule: [python:S2201](https://github.com/SonarSource/sonar-python/blob/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S2201.html)

Action: Proposed individual false-positive disposition after parent review; no remote mutation performed.

### AaGMS_9U7rRJBvbBA1ob

**valid_maintainability_debt** — `python:S3776` at `src/security_lab/batch.py:336`.

load_results verifies schedule/progress, canonical records, run IDs, event state, hashes, JSONL equivalence and PDF provenance. It has many genuine branches that merit a staged readability refactor, not suppression.

Controls / context: Each rejection protects campaign consistency; complexity alone is not evidence of bypass. Preserve explicit interrupted/pending derived-event behavior when separating validation stages.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_batch.BatchTests.test_campaign_reset_hash_checks_and_no_overwrite; tests.test_batch.BatchTests.test_completed_manifest_cannot_claim_missing_runs; tests.test_batch.BatchTests.test_events_have_hash_and_legacy_cross_check

Source: Campaign manifest and canonical/derived evidence

Sink / construct: batch.py:336 load_results

Official rule: [python:S3776](https://github.com/SonarSource/sonar-python/blob/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S3776.html)

Action: Keep finding open for a scoped maintenance change.

### AaGMS_9U7rRJBvbBA1oe

**false_positive** — `pythonsecurity:S8707` at `src/security_lab/batch.py:388`.

The event read is reached from the local CLI campaign input. Its subordinate event filename cannot be chosen freely by imported manifest data.

Controls / context: Run IDs are grammar-validated and unique. The event relative path must exactly equal events/{run_id}.jsonl, then pass _campaign_path containment and symlink rejection. Event bytes are hash checked and parsed events must equal the canonical run record.

Validation: 55 targeted storage tests passed locally. Relevant tests: tests.test_batch.BatchTests.test_events_have_hash_and_legacy_cross_check; tests.test_batch.BatchTests.test_failed_derived_event_write_preserves_canonical_evidence; tests.test_archives.ArchiveTests.test_paths_links_duplicates_and_excessive_expansion_rejected

Source: cli.py:94 and :142 args.directory; load_results

Sink / construct: batch.py:388 event_path.read_bytes()

Rule metadata limit: Official public analyzer rule file returned 404; classification uses actual imported positional flow and inspected trust boundary. Exact official title/prose is not claimed.

Action: Proposed individual false-positive disposition after parent review; no remote mutation performed.

### AaGMS_9H7rRJBvbBA1oM

**valid_maintainability_debt** — `python:S1192` at `src/security_lab/documents.py:140`.

The stored original-PDF filename is repeated between import, hashing and load validation. Current accesses consistently refer to the same protected document member.

Controls / context: No differing literal, lost guard or incorrect runtime outcome was found for this occurrence.

Validation: Source review and tests/test_documents.py: 7 local tests pass.

Official rule: [python:S1192](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S1192.html)

Action: Leave open; no suppression or broad refactor in this change.

### AaGMS_9H7rRJBvbBA1oL

**valid_maintainability_debt** — `python:S1192` at `src/security_lab/documents.py:144`.

The extracted-text filename is repeated between import and verification. A constant could centralize the artifact schema; current paths agree.

Controls / context: No differing literal, lost guard or incorrect runtime outcome was found for this occurrence.

Validation: Source review and tests/test_documents.py: 7 local tests pass.

Official rule: [python:S1192](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S1192.html)

Action: Leave open; no suppression or broad refactor in this change.

### AaGMS_9H7rRJBvbBA1oO

**valid_maintainability_debt** — `python:S1192` at `src/security_lab/documents.py:150`.

The document-metadata filename is repeated between import and reload. A constant could centralize the artifact schema; this finding does not identify invalid metadata validation.

Controls / context: No differing literal, lost guard or incorrect runtime outcome was found for this occurrence.

Validation: Source review and tests/test_documents.py: 7 local tests pass.

Official rule: [python:S1192](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S1192.html)

Action: Leave open; no suppression or broad refactor in this change.

### AaGMS_9H7rRJBvbBA1oP

**valid_maintainability_debt** — `python:S3776` at `src/security_lab/documents.py:158`.

load_document checks the anchored document ID, managed paths, metadata schema, raw/text hashes, extraction identity and confirmation integrity. The numerous checks are appropriate but the function is difficult to maintain.

Controls / context: Keep the validated rejection paths and state invariants; complexity alone is not an exploit demonstration.

Validation: Source review and tests/test_documents.py: 7 local tests pass.

Official rule: [python:S3776](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S3776.html)

Action: Leave open; no suppression or broad refactor in this change.

### AaGMS_9H7rRJBvbBA1oN

**valid_maintainability_debt** — `python:S1192` at `src/security_lab/documents.py:160`.

The confirmation filename is repeated in lookup and confirmation writes. Current names agree and integrity validation is separately enforced.

Controls / context: No differing literal, lost guard or incorrect runtime outcome was found for this occurrence.

Validation: Source review and tests/test_documents.py: 7 local tests pass.

Official rule: [python:S1192](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S1192.html)

Action: Leave open; no suppression or broad refactor in this change.

### AaGMS_9F7rRJBvbBA1oJ

**false_positive** — `python:S6353` at `src/security_lab/hosted.py:28`.

The origin-netloc regular expression deliberately uses ASCII digit ranges, including the optional port. Python Unicode \d also accepts non-ASCII digits, so the recommended shorthand is not behavior-equivalent.

Controls / context: Origins must be HTTPS with no userinfo/path/query/fragment; parsed.port independently enforces numeric range. Keeping the ASCII grammar is intentional defense in depth.

Validation: Local regex probe: example.com:443 accepted, Arabic-digit port rejected by current pattern and accepted after naive \d replacement. Hosted invalid-origin tests pass.

Official rule: [python:S6353](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S6353.html)

Action: Retain the explicit ASCII class; contextual false-positive candidate only, no remote disposition performed.

### AaGMS_9F7rRJBvbBA1oK

**valid_maintainability_debt** — `python:S3776` at `src/security_lab/hosted.py:74`.

HostedAccessMiddleware.__call__ combines ASGI/WebSocket rejection, exact Host/Origin checks, preflight, bearer authentication, CSRF, body limits and response security headers. These branches are deliberate controls but create real maintenance complexity.

Controls / context: Keep the validated rejection paths and state invariants; complexity alone is not an exploit demonstration.

Validation: Source review and tests/test_hosted.py: 12 local tests pass.

Official rule: [python:S3776](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S3776.html)

Action: Leave open; no suppression or broad refactor in this change.

### AaGMS_9F7rRJBvbBA1oH

**valid_maintainability_debt** — `python:S1192` at `src/security_lab/hosted.py:85`.

The ASGI response-start message type is repeated in middleware send paths. Replacing it with a named constant is a consistency improvement, not a failed protocol check.

Controls / context: No differing literal, lost guard or incorrect runtime outcome was found for this occurrence.

Validation: Source review and tests/test_hosted.py: 12 local tests pass.

Official rule: [python:S1192](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S1192.html)

Action: Leave open; no suppression or broad refactor in this change.

### AaGMS_9F7rRJBvbBA1oI

**valid_maintainability_debt** — `python:S1192` at `src/security_lab/hosted.py:147`.

The body-size rejection detail is repeated for declared-length and streamed-length failures. Both paths currently return 413 with consistent meaning.

Controls / context: No differing literal, lost guard or incorrect runtime outcome was found for this occurrence.

Validation: Source review and tests/test_hosted.py: 12 local tests pass.

Official rule: [python:S1192](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S1192.html)

Action: Leave open; no suppression or broad refactor in this change.

### AaGMS_857rRJBvbBA1n8

**reviewed_intended_use** — `python:S8392` at `src/security_lab/hosted_cli.py:51`.

0.0.0.0 is deliberate in the explicitly named production hosted launcher so the Render proxy can reach its process. The ordinary local launcher remains loopback-only. Official rule text permits deliberate production binding with appropriate reverse-proxy/network controls.

Controls / context: HostedSettings validates HTTPS origins, one to eight distinct SHA256 token hashes and workspace configuration before Uvicorn starts. Hosted middleware requires exact public Host/Origin and bearer auth; one worker, reload=False, proxy_headers=False. TLS terminates at the configured hosting proxy (render.yaml/docs).

Validation: tests/test_hosted.py::test_launcher_requires_explicit_workspace_and_safe_port and test_hosted_launcher_runs_one_process_without_proxy_header_trust pass; suite 12/12.

Official rule: [python:S8392](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8392.html)

Action: Retain the intended use and document the contextual review; no remote disposition performed.

### AaGMS_9b7rRJBvbBA1ol

**valid_maintainability_debt** — `python:S3776` at `src/security_lab/jobs.py:93`.

CampaignJobs._discover differentiates generated and legacy directories, symlink/junction rejection, own-worker metadata and damaged/missing manifests. Complexity is real; its defensive cases cannot simply be removed.

Controls / context: Keep the validated rejection paths and state invariants; complexity alone is not an exploit demonstration.

Validation: Source review and tests/test_jobs.py: 10 local tests pass.

Official rule: [python:S3776](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S3776.html)

Action: Leave open; no suppression or broad refactor in this change.

### AaGMS_9b7rRJBvbBA1ok

**valid_maintainability_debt** — `python:S1192` at `src/security_lab/jobs.py:103`.

The campaign manifest filename is repeated in discovery, reading and writing. All current accesses use the same intended filename under their validated campaign root.

Controls / context: No differing literal, lost guard or incorrect runtime outcome was found for this occurrence.

Validation: Source review and tests/test_jobs.py: 10 local tests pass.

Official rule: [python:S1192](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S1192.html)

Action: Leave open; no suppression or broad refactor in this change.

### AaGMS_9b7rRJBvbBA1om

**valid_maintainability_debt** — `python:S3776` at `src/security_lab/jobs.py:258`.

CampaignJobs._listing_fingerprint walks evidence with bounded entry counts, explicit link/junction handling and metadata/error fallbacks. The cache fingerprint is deliberately not the integrity authority; direct brief access revalidates evidence.

Controls / context: Keep the validated rejection paths and state invariants; complexity alone is not an exploit demonstration.

Validation: Source review and tests/test_jobs.py: 10 local tests pass.

Official rule: [python:S3776](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S3776.html)

Action: Leave open; no suppression or broad refactor in this change.

### AaGMS_9b7rRJBvbBA1on

**false_positive** — `python:S7504` at `src/security_lab/jobs.py:340`.

list(self._list_cache) deliberately snapshots OrderedDict keys before stale cache entries are deleted during iteration. Iterating the dictionary directly would raise RuntimeError when its size changes.

Controls / context: Snapshot is bounded by the cache-size cap. It is required for correct stale-entry eviction rather than a redundant iterable conversion.

Validation: test_deleted_record_and_directory_invalidate_and_evict_cache and test_cache_is_bounded_and_oversized_fingerprints_fall_back_to_validation pass; 10/10 jobs tests.

Official rule: [python:S7504](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S7504.html)

Action: Keep the snapshot; no remote disposition performed.

### AaGMS_837rRJBvbBA1nj

**valid_maintainability_debt** — `python:S3776` at `src/security_lab/server.py:45`.

LocalAccessMiddleware.__call__ combines ASGI type handling, Host parsing, Origin/CSRF checks and declared/streamed body limits. Its branching is substantial. The separately reproduced non-ASCII token bug is recorded below, not treated as proof that all complexity reports are vulnerabilities.

Controls / context: Keep the validated rejection paths and state invariants; complexity alone is not an exploit demonstration.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S3776](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S3776.html)

Action: Leave open; no suppression or broad refactor in this change.

### AaGMS_837rRJBvbBA1nk

**false_positive** — `python:S5332` at `src/security_lab/server.py:51`.

The string http:// is prepended to an untrusted Host header solely for urllib.parse.urlsplit. urlsplit is a pure parser; this expression opens no socket and transmits no data.

Controls / context: Parsed hostname must be localhost, 127.0.0.1 or ::1; userinfo/path/query/fragment and malformed ports are rejected. This local-only middleware is distinct from hosted TLS termination.

Validation: test_host_origin_token_and_strict_mock_only_requests passes; the reported expression is parsing, not transport.

Official rule: [python:S5332](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S5332.html)

Action: Retain parsing and guards; contextual false-positive candidate only, no remote disposition performed.

### AaGMS_837rRJBvbBA1nl

**valid_maintainability_debt** — `python:S3776` at `src/security_lab/server.py:151`.

create_app registers many nested routes and helpers, including campaign state, review provenance/versioning and frontend delivery. Extracting cohesive route groups is valid future maintenance work; a broad rewrite would unnecessarily disturb security and scientific invariants in this patch.

Controls / context: Keep the validated rejection paths and state invariants; complexity alone is not an exploit demonstration.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S3776](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S3776.html)

Action: Leave open; no suppression or broad refactor in this change.

### AaGMS_837rRJBvbBA1nt

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:195`.

An unknown campaign ID fails the CampaignJobs lookup; shared helper used by campaign, review and archive routes. The 404 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.

### AaGMS_837rRJBvbBA1nu

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:202`.

Review/archive operations reject an active worker or any manifest state outside the durable terminal-state set. The 409 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.

### AaGMS_837rRJBvbBA1ni

**valid_maintainability_debt** — `python:S1192` at `src/security_lab/server.py:253`.

The private review mapping filename is repeated across review discovery, verification, combine and packet operations. A shared filename constant would prevent future drift; current uses agree.

Controls / context: No differing literal, lost guard or incorrect runtime outcome was found for this occurrence.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S1192](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S1192.html)

Action: Leave open; no suppression or broad refactor in this change.

### AaGMS_837rRJBvbBA1ny

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:281`.

A review API identity failing the anchored identifier grammar is rejected before discovery. The 404 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.

### AaGMS_837rRJBvbBA1nz

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:284`.

Discovery returning zero or more than one matching review identity is rejected rather than selecting an arbitrary path. The 404 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.

### AaGMS_837rRJBvbBA1n0

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:286`.

A discovered review with damaged metadata/provenance is reported as an error instead of used. The 400 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.

### AaGMS_837rRJBvbBA1n3

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:298`.

Reading or adjudicating a review without a combined decision returns a missing-result error. The 404 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.

### AaGMS_837rRJBvbBA1n2

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:310`.

Saving or combining ratings after a combined decision exists is rejected under the shared write lock. The 409 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.

### AaGMS_837rRJBvbBA1nm

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:334`.

Sample PDF lookup rejects a case ID absent from the loaded catalog. The 404 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.

### AaGMS_837rRJBvbBA1nn

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:346`.

Duplicate case, variant or source selections are rejected before work begins. The 400 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.

### AaGMS_837rRJBvbBA1no

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:349`.

The product of selected cases/variants/sources/repeats is rejected when it exceeds 480 tasks. The 400 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.

### AaGMS_837rRJBvbBA1np

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:353`.

An unknown case ID is rejected after catalog loading and before scheduling. The 400 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.

### AaGMS_837rRJBvbBA1nq

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:360`.

A duplicate PDF assignment or assignment outside the requested case/source selection is rejected. The 400 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.

### AaGMS_837rRJBvbBA1nr

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:367`.

Projected repeated article text over 8, 000, 000 characters is rejected before the worker starts. The 400 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.

### AaGMS_837rRJBvbBA1ns

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:372`.

A worker-state conflict raised by jobs.start is converted to a conflict response. The 409 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.

### AaGMS_837rRJBvbBA1nv

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:419`.

A second simultaneous PDF extraction fails the nonblocking semaphore acquisition and closes its upload. The 409 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.

### AaGMS_837rRJBvbBA1nw

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:423`.

A PDF longer than MAX_PDF_BYTES (5 MiB) is rejected; finally closes the file and releases the extraction slot. The 413 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.

### AaGMS_837rRJBvbBA1nx

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:443`.

A finished campaign without any reviewable records cannot produce an empty review export. The 400 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.

### AaGMS_837rRJBvbBA1n1

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:487`.

Duplicate or unknown review IDs in submitted ratings are rejected before version creation. The 400 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.

### AaGMS_837rRJBvbBA1n4

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:542`.

A review set bound to a different campaign is rejected before reviews attach to the requested results. The 400 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.

### AaGMS_837rRJBvbBA1n5

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:555`.

The frontend catch-all rejects api-prefixed paths instead of serving index.html for unknown API endpoints. The 404 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.

### AaGMS_837rRJBvbBA1n6

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:558`.

Traversal components/backslashes are rejected before resolving a frontend file. The 404 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.

### AaGMS_837rRJBvbBA1n7

**valid_maintainability_debt** — `python:S8415` at `src/security_lab/server.py:563`.

A missing requested asset falls back to a guarded index.html; if that too is absent, the response is 404. The 404 response is not declared in endpoint responses metadata.

Controls / context: The runtime HTTPException status is deliberate. FastAPI public docs/OpenAPI routes are disabled at server.py169-170; therefore this is internal API-contract documentation debt, not an exposed Swagger endpoint or incorrect runtime response.

Validation: Source review and tests/test_server.py: 18 local tests pass, including the new malformed-token regression. No claim that every listed status has its own dedicated test.

Official rule: [python:S8415](https://raw.githubusercontent.com/SonarSource/sonar-python/master/python-checks/src/main/resources/org/sonar/l10n/py/rules/python/S8415.html)

Action: Leave open; a later focused API-contract change can add shared/route-specific response metadata without weakening validation.
