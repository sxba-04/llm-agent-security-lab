"""One-off main diagnostics after PR 30; writes require a separately reviewed static pin.

No scanning, code execution, rule/gate changes or automatic disposition learning.
Run only on the isolated ops/sonar-pr30-triage branch. Output excludes messages,
comments, source text, tokens, raw bodies and proxy configuration.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

HOST = "https://sonarcloud.io"
PROJECT = "sxba-04_llm-agent-security-lab"
BRANCH = "main"
REPOSITORY = "sxba-04/llm-agent-security-lab"
OPS_REF = "refs/heads/ops/sonar-pr30-triage"
REVIEWED_REVISION = "58ed94e50013676da212fc0e1fa74590fad216af"
REVIEWED_ANALYSIS = {"key": "e3ce6eb2-cc85-4f61-85e9-5c3c963f234b",
                     "date": "2026-11-06T10:38:09+0000", "revision": REVIEWED_REVISION}
# Apply stays disabled until a fresh read-only run and separate root review.
# Root must approve the exact static file and pin its SHA256 here.
APPROVED_ALLOWLIST_SHA256 = ""
ALLOWLIST = Path(__file__).with_name("sonar_main30_allowlist.json")
OUTPUT = Path("quality-inventory/sonar-main30-triage.json")
MAX_BYTES = 4 * 1024 * 1024
MAX_ISSUES = 500
PAGE_SIZE = 100
KNOWN = {
    "AaGMS_9U7rRJBvbBA1oc": "src/security_lab/batch.py",
    "AaGMS_9j7rRJBvbBA1o-": "src/security_lab/archives.py",
    "AaGwcWxOGbIwpvwBe420": "src/security_lab/cases.py",
}
GET_PATHS = {"issues/search", "project_analyses/search"}
POST_PATHS = {"issues/add_comment", "issues/do_transition"}


class SafeError(Exception):
    """Only local constant diagnostics may leave the process."""


def require(condition, message="Unexpected bounded Sonar response schema."):
    if not condition:
        raise SafeError(message)


def object_value(value):
    require(isinstance(value, dict))
    return value


def text(value, pattern=r"[A-Za-z0-9_.:/-]{1,300}"):
    require(isinstance(value, str) and re.fullmatch(pattern, value) is not None)
    return value


def parse_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate JSON field.")
            result[key] = value
        return result
    def reject(_value):
        raise SafeError("Nonfinite JSON value.")
    try:
        return object_value(json.loads(raw, object_pairs_hook=unique, parse_constant=reject))
    except (ValueError, UnicodeError):
        raise SafeError("Invalid JSON response.") from None


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SafeError("Redirect rejected; no follow-up request sent.")


class Client:
    def __init__(self, token, *, allow_writes=False):
        require(isinstance(token, str) and 1 <= len(token) <= 1024
                and all(33 <= ord(c) <= 126 for c in token), "SONAR_TOKEN missing or malformed.")
        self._token = token
        self.allow_writes = allow_writes
        # Retain organizational proxy/TLS defaults; never inspect or print them.
        self.opener = build_opener(NoRedirects())

    def request(self, endpoint, parameters, *, post=False):
        require(endpoint in (POST_PATHS if post else GET_PATHS), "Endpoint not allowed.")
        require(not post or self.allow_writes, "Read-only mode prohibits POST.")
        if post:
            require(parameters.get("issue") in KNOWN, "POST issue is outside the three reviewed IDs.")
            expected = {"issue", "text"} if endpoint == "issues/add_comment" else {"issue", "transition"}
            require(set(parameters) == expected, "Unexpected POST parameters.")
            if endpoint == "issues/do_transition":
                require(parameters["transition"] == "falsepositive", "Transition not allowed.")
        encoded = urlencode(parameters).encode("utf-8")
        url = HOST + "/api/" + endpoint
        if not post:
            url += "?" + encoded.decode("ascii")
        headers = {"Authorization": "Bearer " + self._token, "Accept": "application/json"}
        if post:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = Request(url, data=encoded if post else None, headers=headers,
                          method="POST" if post else "GET")
        try:
            with self.opener.open(request, timeout=20) as response:
                require(response.status == 200 and response.geturl() == url,
                        "Unexpected HTTP status or URL; request stopped.")
                raw = response.read(MAX_BYTES + 1)
            require(len(raw) <= MAX_BYTES, "Response size limit exceeded.")
            return parse_json(raw)
        except HTTPError as error:
            if error.code in {401, 403}:
                raise SafeError("Sonar authentication/permission denied; no automatic retry.") from None
            raise SafeError("Sonar HTTP request failed; outcome may require read-only reconciliation.") from None
        except (OSError, ValueError):
            raise SafeError("Sonar transport failed; no automatic retry or remote body output.") from None


def latest_analysis(client):
    result = client.request("project_analyses/search",
                            {"project": PROJECT, "branch": BRANCH, "p": 1, "ps": 1})
    rows = result.get("analyses")
    require(isinstance(rows, list) and len(rows) == 1, "Latest main analysis not uniquely available.")
    row = object_value(rows[0])
    # Project/branch select the endpoint scope; validate them too if returned.
    require(row.get("project", PROJECT) == PROJECT and row.get("branch", BRANCH) == BRANCH,
            "Analysis outside fixed project/main scope.")
    require(not row.get("pullRequest"), "PR analysis cannot authorize a main operation.")
    return {"key": text(row.get("key"), r"[A-Za-z0-9_-]{1,100}"),
            "date": text(row.get("date"), r"[0-9T:+.Z-]{10,40}"),
            "revision": text(row.get("revision"), r"[0-9a-f]{40}")}


def require_reviewed_analysis(stamp):
    require(stamp == REVIEWED_ANALYSIS, "Server analysis key/date/revision differs from reviewed main snapshot.")


def project_issue(row):
    row = object_value(row)
    require(row.get("project") == PROJECT, "Issue outside fixed project.")
    require(not row.get("pullRequest") and row.get("branch", BRANCH) == BRANCH,
            "Issue outside fixed main branch.")
    component = text(row.get("component"))
    require(component.startswith(PROJECT + ":"), "Issue component outside project.")
    transitions = row.get("transitions", [])
    require(isinstance(transitions, list) and len(transitions) <= 32)
    result = {"key": text(row.get("key")), "rule": text(row.get("rule")),
              "component": component, "project": PROJECT,
              "transitions": sorted(text(v, r"[a-z]{1,40}") for v in transitions)}
    for field in ("status", "resolution", "issueStatus", "type"):
        if field in row:
            result[field] = text(row[field], r"[A-Z_-]{1,40}")
    flows = row.get("flows", [])
    require(isinstance(flows, list) and len(flows) <= 100)
    result["flows"] = []
    for flow in flows:
        locations = object_value(flow).get("locations", [])
        require(isinstance(locations, list) and len(locations) <= 100)
        safe_locations = []
        for location in locations:
            location = object_value(location)
            selected = {}
            if "component" in location:
                component = text(location["component"])
                require(component.startswith(PROJECT + ":"), "Flow location outside project.")
                selected["component"] = component
            if "textRange" in location:
                span = object_value(location["textRange"])
                selected["textRange"] = {}
                for name in ("startLine", "endLine", "startOffset", "endOffset"):
                    if name in span:
                        require(type(span[name]) is int and 0 <= span[name] <= 10_000_000)
                        selected["textRange"][name] = span[name]
            safe_locations.append(selected)
        result["flows"].append({"locations": safe_locations})
    return result


def inventory(client, keys=None):
    found = {}; total = None
    for page in range(1, MAX_ISSUES // PAGE_SIZE + 1):
        params = {"componentKeys": PROJECT, "branch": BRANCH,
                  "additionalFields": "transitions", "ps": PAGE_SIZE, "p": page}
        if keys is not None:
            params["issues"] = ",".join(sorted(keys))
        value = client.request("issues/search", params)
        paging = object_value(value.get("paging"))
        count = paging.get("total")
        require(type(count) is int and 0 <= count <= MAX_ISSUES, "Issue inventory exceeds fixed bound.")
        require(paging.get("pageIndex") == page and paging.get("pageSize") == PAGE_SIZE)
        require(total is None or total == count, "Issue inventory changed during pagination.")
        total = count
        rows = value.get("issues")
        require(isinstance(rows, list) and len(rows) <= PAGE_SIZE)
        for raw in rows:
            row = project_issue(raw)
            require(row["key"] not in found, "Duplicate issue in inventory.")
            require(keys is None or row["key"] in keys, "Unexpected issue from filtered request.")
            found[row["key"]] = row
        if len(found) == total:
            return found
        require(rows and len(found) < total, "Incomplete issue inventory.")
    raise SafeError("Issue inventory pagination limit exceeded.")


def load_allowlist(path=ALLOWLIST):
    require(not path.is_symlink() and path.is_file() and path.stat().st_size <= 64 * 1024,
            "Static allowlist missing or oversized.")
    raw = path.read_bytes()
    data = parse_json(raw)
    require(data.get("project") == PROJECT and data.get("branch") == BRANCH and "pull_request" not in data)
    require(data.get("reviewed_revision") == REVIEWED_REVISION)
    entries = data.get("issues")
    require(isinstance(entries, list) and len(entries) == len(KNOWN), "Exactly three reviewed issue IDs required.")
    by_key = {}
    for entry in entries:
        entry = object_value(entry); key = entry.get("key")
        require(key in KNOWN and key not in by_key, "Unknown or duplicate disposition ID.")
        require(entry.get("component") == PROJECT + ":" + KNOWN[key], "Disposition component mismatch.")
        require(entry.get("transition") == "falsepositive", "Only reviewed falsepositive transitions allowed.")
        require(isinstance(entry.get("comment"), str) and 100 <= len(entry["comment"]) <= 6000
                and REVIEWED_REVISION in entry["comment"], "Concrete pinned evidence comment required.")
        by_key[key] = entry
    return data, by_key, hashlib.sha256(raw).hexdigest()


def false_positive(row):
    legacy = row.get("resolution") == "FALSE-POSITIVE" and row.get("status") in {"RESOLVED", "CLOSED"}
    if "issueStatus" not in row:
        return legacy
    modern = row["issueStatus"] == "FALSE_POSITIVE"
    if "resolution" in row:
        require(modern == (row["resolution"] == "FALSE-POSITIVE"), "Contradictory issue status representations.")
    if modern and "status" in row:
        require(row["status"] in {"RESOLVED", "CLOSED"}, "Contradictory issue status representations.")
    require(not legacy or modern, "Contradictory issue status representations.")
    return modern


def validate_apply(data, entries, digest, current, stamp):
    require(APPROVED_ALLOWLIST_SHA256 and digest == APPROVED_ALLOWLIST_SHA256
            and data.get("approved") is True, "Apply disabled: reviewed static allowlist SHA256 not pinned.")
    require_reviewed_analysis(stamp)
    require(data.get("expected_analysis") == stamp, "Analysis differs from reviewed read-only snapshot.")
    require(set(current) >= set(KNOWN), "Reviewed issue absent; reconcile read-only before applying.")
    for key, entry in entries.items():
        rule = text(entry.get("rule"))
        require(current[key]["rule"] == rule and current[key]["component"] == entry["component"],
                "Issue rule/component differs from reviewed static disposition.")
        require(false_positive(current[key]) or "falsepositive" in current[key]["transitions"],
                "Required issue transition unavailable; check Administer Issues permission.")


def before_post(client, data, entries, digest, stamp):
    """Recheck every selected identity and the full analysis immediately before POST."""
    require(latest_analysis(client) == stamp, "Analysis changed before mutation; POST withheld.")
    current = inventory(client, set(KNOWN))
    validate_apply(data, entries, digest, current, stamp)
    require(latest_analysis(client) == stamp, "Analysis changed during pre-mutation read; POST withheld.")
    return current


def run(client, data, entries, digest, report, apply=False):
    stamp = latest_analysis(client)
    before = inventory(client)
    require(latest_analysis(client) == stamp, "Analysis changed during read-only inventory.")
    report.update(analysis=stamp, inventory=list(before.values()),
                  selected_ids=sorted(KNOWN), missing_selected_ids=sorted(set(KNOWN)-set(before)),
                  allowlist_sha256=digest, reviewed_revision=REVIEWED_REVISION,
                  revision_verified_by_server=stamp["revision"] == REVIEWED_REVISION,
                  reviewed_analysis_matches=stamp == REVIEWED_ANALYSIS)
    if not apply:
        return
    validate_apply(data, entries, digest, before, stamp)
    for key in sorted(KNOWN):
        fresh = before_post(client, data, entries, digest, stamp)
        row = fresh[key]; entry = entries[key]
        item = {"key": key, "state": "already_false_positive" if false_positive(row) else "ready"}
        report["mutations"].append(item)
        if false_positive(row):
            continue
        require("falsepositive" in row["transitions"], "Issue transition no longer available.")
        item["state"] = "comment_attempted"
        comment = client.request("issues/add_comment", {"issue": key, "text": entry["comment"]}, post=True)
        require(object_value(comment.get("issue")).get("key") == key, "Comment response identity mismatch.")
        item["state"] = "comment_confirmed"
        row = before_post(client, data, entries, digest, stamp)[key]
        if false_positive(row):
            item["state"] = "false_positive_observed_after_comment"
            continue
        require("falsepositive" in row["transitions"], "Issue transition no longer available.")
        item["state"] = "transition_attempted"
        transition = client.request("issues/do_transition", {"issue": key, "transition": "falsepositive"}, post=True)
        require(object_value(transition.get("issue")).get("key") == key, "Transition response identity mismatch.")
        after = inventory(client, {key})
        require(set(after) == {key} and false_positive(after[key]), "False-positive status not verified after transition.")
        require(after[key]["rule"] == entry["rule"] and after[key]["component"] == entry["component"], "Post-transition identity mismatch.")
        item["state"] = "false_positive_verified"
    require(latest_analysis(client) == stamp, "Analysis changed before final verification.")
    final = inventory(client, set(KNOWN))
    require(set(final) == set(KNOWN) and all(false_positive(row) for row in final.values()),
            "Final selected issue status verification failed.")
    require(all(row["rule"] == entries[key]["rule"] and row["component"] == entries[key]["component"]
                for key, row in final.items()), "Final selected issue identity verification failed.")
    require(latest_analysis(client) == stamp, "Analysis changed during final verification.")
    report["final_selected"] = list(final.values())


def branch_guard():
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY
            and os.environ.get("GITHUB_REPOSITORY_OWNER") == "sxba-04"
            and os.environ.get("GITHUB_ACTOR") == "sxba-04"
            and os.environ.get("GITHUB_REF") == OPS_REF
            and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch",
            "Runner requires owner dispatch on the fixed isolated operations branch.")


def deadline(_signal, _frame):
    raise SafeError("Operation deadline exceeded; no automatic retry.")


def redact(value, token):
    """Defense in depth even if a trusted upstream echoes a token in an ID."""
    if isinstance(value, str):
        return value.replace(token, "[REDACTED]") if token else value
    if isinstance(value, list):
        return [redact(item, token) for item in value]
    if isinstance(value, dict):
        return {redact(key, token): redact(item, token) for key, item in value.items()}
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Requires committed reviewed allowlist SHA256; otherwise refused.")
    args = parser.parse_args(argv)
    report = {"schema_version": 1, "project": PROJECT, "branch": BRANCH,
              "mode": "apply" if args.apply else "read_only", "mutations": [], "success": False,
              "created_at": datetime.now(timezone.utc).isoformat()}
    # Reserve the receipt before any network request. Existing receipts must
    # never cause remote changes followed by an output-publication failure.
    try:
        OUTPUT.parent.mkdir(exist_ok=True)
        stream = OUTPUT.open("x", encoding="utf-8")
    except OSError:
        print("Cannot reserve sanitized receipt; no remote requests made.", file=sys.stderr)
        return 1
    try:
        branch_guard()
        data, entries, digest = load_allowlist()
        signal.signal(signal.SIGALRM, deadline); signal.alarm(240)
        client = Client(os.environ.get("SONAR_TOKEN", ""), allow_writes=args.apply)
        run(client, data, entries, digest, report, args.apply)
        report["success"] = True
    except SafeError as error:
        report["error"] = str(error)
    except Exception:
        report["error"] = "Unexpected local failure; no raw exception or remote body emitted."
    finally:
        signal.alarm(0)
    try:
        with stream:
            json.dump(redact(report, os.environ.get("SONAR_TOKEN", "")), stream, ensure_ascii=True, indent=2)
            stream.write("\n")
    except OSError:
        print("Cannot preserve sanitized receipt; no successful completion claimed.", file=sys.stderr)
        return 1
    print("Sanitized main receipt saved. " + ("Completed." if report["success"] else "Stopped; inspect receipt before retry."))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
