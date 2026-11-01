"""Read-only, bounded SonarCloud main-branch inventory; no scanner or mutations."""
from __future__ import annotations

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
ENDPOINTS = frozenset({"issues/search", "measures/component", "qualitygates/project_status", "project_analyses/search"})
METRICS = ("coverage", "line_coverage", "branch_coverage", "lines_to_cover", "uncovered_lines",
           "conditions_to_cover", "uncovered_conditions", "duplicated_lines_density", "ncloc")


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


def unresolved_issues(client) -> list[dict]:
    result, seen, total, page = [], set(), None, 1
    while True:
        response = client.get("issues/search", {"componentKeys": PROJECT, "branch": BRANCH,
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


def measures(client) -> dict:
    response = client.get("measures/component", {"component": PROJECT, "branch": BRANCH,
                                                "metricKeys": ",".join(METRICS)})
    source = object_value(response.get("component"))
    if source.get("key") != PROJECT:
        raise InventoryError("Sonar measures do not identify the configured project.")
    result = {}
    for entry in list_value(source.get("measures")):
        entry = object_value(entry)
        metric = text_value(entry.get("metric"))
        if metric not in METRICS or metric in result:
            raise InventoryError("Unexpected or duplicate Sonar metric.")
        result[metric] = text_value(entry.get("value"))
    return {"values": result, "missing_metrics": [metric for metric in METRICS if metric not in result]}


def quality_gate(client) -> dict:
    response = client.get("qualitygates/project_status", {"projectKey": PROJECT, "branch": BRANCH})
    source = object_value(response.get("projectStatus"))
    result = {"status": text_value(source.get("status")), "conditions": []}
    for condition in list_value(source.get("conditions")):
        result["conditions"].append(select_text(object_value(condition),
                                   ("status", "metricKey", "comparator", "errorThreshold", "actualValue")))
    return result


def collect(client) -> dict:
    before = latest_analysis(client)
    issues = unresolved_issues(client)
    metric_values = measures(client)
    gate = quality_gate(client)
    if latest_analysis(client) != before:
        raise InventoryError("Sonar analysis changed during collection; rerun the inventory.")
    return {"schema_version": 1, "project": PROJECT, "branch": BRANCH,
            "collected_at": datetime.now(timezone.utc).isoformat(), "source": HOST,
            "analysis": before, "issue_filter": {"resolved": False}, "issue_count": len(issues),
            "issues": issues, "measures": metric_values, "quality_gate": gate,
            "limitations": ["A read-only observation, not a security verdict or immutable server snapshot.",
                            "Concurrent issue edits may occur without a new analysis.",
                            "Only unresolved main-branch issues are included; no PR, closed-issue or source-code export."]}


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


def main() -> int:
    try:
        if OUTPUT.exists() or OUTPUT.is_symlink():
            raise InventoryError("Inventory output already exists; it will not be replaced.")
        token = os.environ.get("SONAR_TOKEN", "")
        report = collect(SonarClient(token))
        publish(report, token, OUTPUT)
    except InventoryError as error:
        print(str(error), file=sys.stderr)
        return 1
    except OSError:
        print("Inventory output could not be published.", file=sys.stderr)
        return 1
    print("Sonar main inventory complete; sanitized JSON artifact is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
