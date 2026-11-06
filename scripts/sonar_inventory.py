"""Read-only, bounded SonarCloud main/PR inventory; no scanner or mutations."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

HOST = "https://sonarcloud.io"
PROJECT = "sxba-04_llm-agent-security-lab"
BRANCH = "main"
PAGE_SIZE = 100
MAX_ISSUES = 10_000
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
OUTPUT = Path("quality-inventory/sonar-main.json")
PR_OUTPUT = Path("quality-inventory/sonar-pr.json")
ENDPOINTS = frozenset({"issues/search", "measures/component", "qualitygates/project_status",
                       "project_analyses/search", "project_pull_requests/list"})
METRICS = ("coverage", "line_coverage", "branch_coverage", "lines_to_cover", "uncovered_lines",
           "conditions_to_cover", "uncovered_conditions", "duplicated_lines_density", "ncloc")
PR_METRICS = METRICS + ("new_coverage", "new_line_coverage", "new_branch_coverage", "new_lines_to_cover",
                        "new_uncovered_lines", "new_conditions_to_cover", "new_uncovered_conditions",
                        "new_duplicated_lines_density", "new_lines")


def revision_value(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", value):
        raise InventoryError("Expected a complete Git revision.")
    return value.lower()


def analysis_scope(pull_request: int | None) -> dict:
    if pull_request is None:
        return {"branch": BRANCH}
    if type(pull_request) is not int or not 1 <= pull_request <= 2**31 - 1:
        raise InventoryError("Pull request must be a positive integer.")
    return {"pullRequest": str(pull_request)}


class InventoryError(Exception):
    """Messages are local constants; never include upstream bodies or credentials."""


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise InventoryError("Sonar redirected a request; inventory stopped.")


class SonarClient:
    def __init__(self, token: str):
        if not token or len(token) > 1024 or any(char.isspace() for char in token):
            raise InventoryError("SONAR_TOKEN is missing or malformed.")
        self.token = token
        self.opener = build_opener(NoRedirects())

    def get(self, endpoint: str, parameters: dict) -> dict:
        if endpoint not in ENDPOINTS:
            raise InventoryError("Unsupported Sonar endpoint.")
        url = HOST + "/api/" + endpoint + "?" + urlencode(parameters)
        request = Request(url, headers={"Authorization": "Bearer " + self.token,
                                       "Accept": "application/json"}, method="GET")
        try:
            with self.opener.open(request, timeout=30) as response:
                if response.status != 200 or response.geturl() != url:
                    raise InventoryError("Unexpected Sonar response or redirect.")
                payload = response.read(MAX_RESPONSE_BYTES + 1)
            if len(payload) > MAX_RESPONSE_BYTES:
                raise InventoryError("Sonar response exceeds the inventory size limit.")
            value = json.loads(payload)
        except HTTPError as error:
            raise InventoryError(f"Sonar request failed (HTTP {error.code}); no inventory published.") from None
        except (OSError, ValueError):
            raise InventoryError("Sonar transport or JSON response failed; no inventory published.") from None
        return object_value(value)


def object_value(value) -> dict:
    if not isinstance(value, dict):
        raise InventoryError("Unexpected Sonar object schema.")
    return value


def list_value(value) -> list:
    if not isinstance(value, list):
        raise InventoryError("Unexpected Sonar list schema.")
    return value


def text_value(value) -> str:
    if not isinstance(value, str) or not value or len(value) > 20_000:
        raise InventoryError("Unexpected Sonar text schema.")
    return value


def integer_value(value, minimum=0) -> int:
    if type(value) is not int or value < minimum:
        raise InventoryError("Unexpected Sonar integer schema.")
    return value


def select_text(source: dict, names: tuple[str, ...]) -> dict:
    return {name: text_value(source[name]) for name in names if name in source}


def component(value) -> str:
    value = text_value(value)
    if value != PROJECT and not value.startswith(PROJECT + ":"):
        raise InventoryError("Sonar returned a component outside the configured project.")
    return value


def location(value: dict) -> dict:
    source = object_value(value)
    result = {}
    if "component" in source:
        result["component"] = component(source["component"])
    if "textRange" in source:
        span = object_value(source["textRange"])
        result["textRange"] = {key: integer_value(span[key]) for key in
                               ("startLine", "endLine", "startOffset", "endOffset") if key in span}
    return result


def issue(value) -> dict:
    source = object_value(value)
    if source.get("project") != PROJECT:
        raise InventoryError("Sonar returned an issue outside the configured project.")
    # Diagnostic messages can quote source literals, secrets or personal data.
    # Export stable identifiers and positions, never upstream free-text messages.
    result = {name: text_value(source.get(name)) for name in ("key", "rule")}
    result["component"] = component(source.get("component"))
    result.update(select_text(source, ("type", "severity", "status", "issueStatus")))
    if not ("status" in result or "issueStatus" in result):
        raise InventoryError("Sonar issue status is missing.")
    if "line" in source:
        result["line"] = integer_value(source["line"], 1)
    if "textRange" in source:
        result["textRange"] = location({"textRange": source["textRange"]})["textRange"]
    result["flows"] = []
    for flow in list_value(source.get("flows", [])):
        flow = object_value(flow)
        result["flows"].append({"locations": [location(item) for item in list_value(flow.get("locations"))]})
    if "impacts" in source:
        result["impacts"] = [{name: text_value(object_value(impact).get(name))
                              for name in ("softwareQuality", "severity")}
                             for impact in list_value(source["impacts"])]
    return result


def latest_analysis(client) -> dict:
    response = client.get("project_analyses/search", {"project": PROJECT, "branch": BRANCH, "p": 1, "ps": 1})
    analyses = list_value(response.get("analyses"))
    if not analyses:
        raise InventoryError("No main-branch Sonar analysis is available.")
    source = object_value(analyses[0])
    result = {key: text_value(source.get(key)) for key in ("key", "date", "revision")}
    if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", result["revision"]):
        raise InventoryError("Sonar analysis has no complete Git revision.")
    return result


def pull_request_analysis(client, pull_request: int) -> dict:
    response = client.get("project_pull_requests/list", {"project": PROJECT})
    entries = list_value(response.get("pullRequests"))
    if len(entries) > MAX_ISSUES:
        raise InventoryError("Sonar PR listing exceeds the inventory size limit.")
    matching = [object_value(entry) for entry in entries if object_value(entry).get("key") == str(pull_request)]
    if len(matching) != 1:
        raise InventoryError("Exactly one analyzed Sonar pull request is required.")
    source = matching[0]
    date = text_value(source.get("analysisDate"))
    try:
        parsed = datetime.fromisoformat(date)
    except ValueError:
        raise InventoryError("Sonar PR analysis date is malformed.") from None
    if parsed.tzinfo is None:
        raise InventoryError("Sonar PR analysis date must include its timezone.")
    return {"pull_request": pull_request, "analysis_date": date,
            "quality_gate_status": text_value(object_value(source.get("status")).get("qualityGateStatus"))}


def scanner_submission(path: Path) -> dict:
    with path.open("rb") as stream:
        raw = stream.read(32769)
    if len(raw) > 32768:
        raise InventoryError("Scanner submission receipt exceeds the size limit.")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeError:
        raise InventoryError("Scanner submission receipt is malformed.") from None
    fields = {}
    for line in lines:
        key, separator, value = line.partition("=")
        if key not in {"projectKey", "serverUrl", "ceTaskId"}:
            continue
        if not separator or key in fields:
            raise InventoryError("Scanner submission receipt has duplicate or missing fields.")
        fields[key] = value
    if fields.get("projectKey") != PROJECT or fields.get("serverUrl", "").rstrip("/") != HOST:
        raise InventoryError("Scanner submission receipt does not match the configured project/host.")
    task = fields.get("ceTaskId", "")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,200}", task):
        raise InventoryError("Scanner submission receipt has no valid task identifier.")
    return {"ce_task_id": task, "source": "local scanner submission receipt; task not queried on server"}


def unresolved_issues(client, pull_request: int | None = None) -> list[dict]:
    result, seen, total, page = [], set(), None, 1
    while True:
        response = client.get("issues/search", {"componentKeys": PROJECT, **analysis_scope(pull_request),
                              "resolved": "false", "p": page, "ps": PAGE_SIZE})
        paging = object_value(response.get("paging"))
        current_total = integer_value(paging.get("total"))
        if (integer_value(paging.get("pageIndex"), 1) != page
                or integer_value(paging.get("pageSize"), 1) != PAGE_SIZE
                or current_total > MAX_ISSUES or (total is not None and total != current_total)):
            raise InventoryError("Sonar pagination changed or exceeds the complete-inventory limit.")
        total = current_total
        rows = list_value(response.get("issues"))
        if len(rows) != min(PAGE_SIZE, total - len(result)):
            raise InventoryError("Sonar returned an incomplete issue page.")
        for row in rows:
            item = issue(row)
            if item["key"] in seen:
                raise InventoryError("Sonar returned duplicate issues across pages.")
            seen.add(item["key"])
            result.append(item)
        if len(result) == total:
            return result
        page += 1


def measures(client, pull_request: int | None = None) -> dict:
    requested = PR_METRICS if pull_request is not None else METRICS
    response = client.get("measures/component", {"component": PROJECT, **analysis_scope(pull_request),
                                                "metricKeys": ",".join(requested)})
    source = object_value(response.get("component"))
    if source.get("key") != PROJECT:
        raise InventoryError("Sonar measures do not identify the configured project.")
    result, periods, seen = {}, {}, set()
    for entry in list_value(source.get("measures")):
        entry = object_value(entry)
        metric = text_value(entry.get("metric"))
        if metric not in requested or metric in seen:
            raise InventoryError("Unexpected or duplicate Sonar metric.")
        seen.add(metric)
        _measure_value(entry, metric, result, periods)
    return {"values": result, "period_values": periods,
            "missing_metrics": [metric for metric in requested if metric not in seen]}


def _measure_value(entry: dict, metric: str, values: dict, periods: dict) -> None:
    if "value" in entry:
        values[metric] = text_value(entry["value"])
    if "period" in entry:
        periods[metric] = text_value(object_value(entry["period"]).get("value"))
    if metric not in values and metric not in periods:
        raise InventoryError("Sonar metric has neither a value nor a period value.")


def quality_gate(client, pull_request: int | None = None) -> dict:
    response = client.get("qualitygates/project_status", {"projectKey": PROJECT, **analysis_scope(pull_request)})
    source = object_value(response.get("projectStatus"))
    result = {"status": text_value(source.get("status")), "conditions": []}
    for condition in list_value(source.get("conditions")):
        result["conditions"].append(select_text(object_value(condition),
                                   ("status", "metricKey", "comparator", "errorThreshold", "actualValue")))
    return result


def collect(client, *, pull_request: int | None = None, expected_revision: str | None = None,
            scanner_report: Path | None = None) -> dict:
    analysis_scope(pull_request)  # Validate scope before any network request.
    expected = revision_value(expected_revision) if expected_revision is not None else None
    if pull_request is not None and expected is None:
        raise InventoryError("PR inventory requires an explicit expected revision.")
    receipt = scanner_submission(scanner_report) if scanner_report is not None else None
    observe = latest_analysis if pull_request is None else lambda api: pull_request_analysis(api, pull_request)
    before = observe(client)
    if pull_request is None and expected is not None and before["revision"].lower() != expected:
        raise InventoryError("Sonar main analysis does not match the expected revision.")
    issues = unresolved_issues(client, pull_request)
    metric_values = measures(client, pull_request)
    gate = quality_gate(client, pull_request)
    if pull_request is not None and gate["status"] != before["quality_gate_status"]:
        raise InventoryError("Sonar PR listing and quality gate disagree; rerun the inventory.")
    if observe(client) != before:
        raise InventoryError("Sonar analysis changed during collection; rerun the inventory.")
    report = {"schema_version": 1, "project": PROJECT,
            **({"branch": BRANCH} if pull_request is None else {"pull_request": pull_request}),
            "collected_at": datetime.now(timezone.utc).isoformat(), "source": HOST,
            "analysis": before, "issue_filter": {"resolved": False}, "issue_count": len(issues),
            "issues": issues, "measures": metric_values, "quality_gate": gate,
            "limitations": ["A read-only observation, not a security verdict or immutable server snapshot.",
                            "Concurrent issue edits may occur without a new analysis.",
                            "Only unresolved issues in the selected scope are included; no closed-issue or source-code export."]}
    if pull_request is not None:
        report["scan_context"] = {"expected_revision": expected, "server_revision_verified": False,
                                  "revision_source": "explicit CI/caller input, not supplied by PR listing API"}
        report["limitations"].append("PR analysis may predate the current scanner submission; expected revision and CE receipt do not prove server revision identity.")
    if receipt is not None:
        report["scanner_submission"] = receipt
    return report


def publish(report: dict, token: str, output: Path) -> None:
    # Redact an echoed credential even if it occurs in an upstream diagnostic.
    payload = json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False)
    payload = payload.replace(json.dumps(token, ensure_ascii=True)[1:-1], "[REDACTED]") + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=".sonar-inventory-", suffix=".tmp", dir=output.parent)
    temporary = Path(name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def options(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pull-request", type=int)
    parser.add_argument("--expected-revision")
    parser.add_argument("--scanner-report", type=Path)
    args = parser.parse_args(argv)
    try:
        analysis_scope(args.pull_request)
        if args.expected_revision is not None:
            revision_value(args.expected_revision)
        if args.pull_request is not None and args.expected_revision is None:
            raise InventoryError("PR inventory requires --expected-revision.")
    except InventoryError as error:
        parser.error(str(error))
    return args


def main(argv: list[str] | None = None) -> int:
    args = options(argv)
    output = PR_OUTPUT if args.pull_request is not None else OUTPUT
    try:
        if output.exists() or output.is_symlink():
            raise InventoryError("Inventory output already exists; it will not be replaced.")
        token = os.environ.get("SONAR_TOKEN", "")
        report = collect(SonarClient(token), pull_request=args.pull_request,
                         expected_revision=args.expected_revision, scanner_report=args.scanner_report)
        publish(report, token, output)
    except InventoryError as error:
        print(str(error), file=sys.stderr)
        return 1
    except OSError:
        print("Inventory output could not be published.", file=sys.stderr)
        return 1
    print("Sonar inventory complete for the selected scope; sanitized JSON artifact is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
