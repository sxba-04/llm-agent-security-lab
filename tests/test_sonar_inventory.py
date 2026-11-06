"""Read-only inventory boundaries, using only local mocked Sonar responses."""
import copy
import importlib.util
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

SPEC = importlib.util.spec_from_file_location(
    "sonar_inventory", Path(__file__).resolve().parents[1] / "scripts" / "sonar_inventory.py")
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)


def sample_issue(key):
    return {"key": key, "project": inventory.PROJECT, "rule": "python:S0000",
            "component": inventory.PROJECT + ":src/example.py", "line": 4,
            "message": "Synthetic diagnostic", "type": "CODE_SMELL", "severity": "MAJOR",
            "status": "OPEN", "author": "private@example.test", "assignee": "private-user",
            "comments": [{"markdown": "Private discussion"}],
            "flows": [{"locations": [{"component": inventory.PROJECT + ":src/example.py",
                                       "textRange": {"startLine": 4, "endLine": 5}, "msg": "Synthetic location",
                                       "source": "private source snippet"}]}]}


class FakeSonar:
    def __init__(self):
        self.requests = []
        self.rows = [sample_issue("one"), sample_issue("two"), sample_issue("three")]
        self.analysis = {"key": "analysis-key", "date": "2026-11-01T12:00:00Z", "revision": "a" * 40,
                         "events": [{"name": "Private event"}]}
        self.pull_request = {"key": "30", "analysisDate": "2026-11-06T10:00:00+0000",
                             "status": {"qualityGateStatus": "OK"}, "title": "Private PR title",
                             "branch": "private-branch-name"}

    def get(self, endpoint, parameters):
        self.requests.append((endpoint, parameters))
        if endpoint == "project_analyses/search":
            return {"analyses": [copy.deepcopy(self.analysis)]}
        if endpoint == "project_pull_requests/list":
            return {"pullRequests": [copy.deepcopy(self.pull_request)]}
        if endpoint == "issues/search":
            page, size = parameters["p"], parameters["ps"]
            return {"paging": {"total": len(self.rows), "pageIndex": page, "pageSize": size},
                    "issues": copy.deepcopy(self.rows[(page - 1) * size:page * size])}
        if endpoint == "measures/component":
            return {"component": {"key": inventory.PROJECT, "measures": [{"metric": "coverage", "value": "88.9"}]}}
        if endpoint == "qualitygates/project_status":
            return {"projectStatus": {"status": "OK", "conditions": []}}
        raise AssertionError("Unexpected endpoint")


class SonarInventoryTests(unittest.TestCase):
    def test_pr_inventory_uses_pr_scope_and_does_not_claim_server_revision(self):
        client = FakeSonar()
        with patch.object(inventory, "PAGE_SIZE", 2):
            report = inventory.collect(client, pull_request=30, expected_revision="b" * 40)
        self.assertEqual(report["pull_request"], 30)
        self.assertNotIn("branch", report)
        self.assertEqual(report["analysis"]["analysis_date"], client.pull_request["analysisDate"])
        self.assertNotIn("revision", report["analysis"])
        self.assertEqual(report["scan_context"]["expected_revision"], "b" * 40)
        self.assertFalse(report["scan_context"]["server_revision_verified"])
        self.assertEqual(report["issue_count"], 3)
        for endpoint, parameters in client.requests:
            self.assertNotEqual(endpoint, "project_analyses/search")
            self.assertNotIn("branch", parameters)
            if endpoint != "project_pull_requests/list":
                self.assertEqual(parameters["pullRequest"], "30")
        serialized = json.dumps(report)
        for private in ("Private PR title", "private-branch-name", "Private discussion"):
            self.assertNotIn(private, serialized)

    def test_pr_scope_requires_positive_number_and_full_expected_revision_before_requests(self):
        for number, revision in ((0, "a" * 40), (-1, "a" * 40), (True, "a" * 40),
                                 (30, None), (30, "short"), (30, "x" * 40)):
            client = FakeSonar()
            with self.subTest(number=number, revision=revision), self.assertRaises(inventory.InventoryError):
                inventory.collect(client, pull_request=number, expected_revision=revision)
            self.assertEqual(client.requests, [])
        with self.assertRaisesRegex(inventory.InventoryError, "does not match"):
            inventory.collect(FakeSonar(), expected_revision="b" * 40)

    def test_pr_missing_analysis_and_changing_analysis_reject_partial_inventory(self):
        for field, value in (("key", "31"), ("analysisDate", None),
                             ("analysisDate", "2026-11-06T10:00:00"), ("analysisDate", "bad-date")):
            client = FakeSonar()
            client.pull_request[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(inventory.InventoryError):
                inventory.collect(client, pull_request=30, expected_revision="a" * 40)
        client = FakeSonar()
        original = client.get
        def change_date(endpoint, parameters):
            if endpoint == "qualitygates/project_status":
                client.pull_request["analysisDate"] = "2026-11-06T11:00:00Z"
            return original(endpoint, parameters)
        with patch.object(client, "get", side_effect=change_date):
            with self.assertRaisesRegex(inventory.InventoryError, "changed during collection"):
                inventory.collect(client, pull_request=30, expected_revision="a" * 40)

    def test_new_code_period_values_are_distinct_and_missing_values_not_zero(self):
        client = MagicMock()
        client.get.return_value = {"component": {"key": inventory.PROJECT, "measures": [
            {"metric": "coverage", "value": "91.2"},
            {"metric": "new_coverage", "period": {"value": "79.5", "index": 1, "private": "ignored"}},
        ]}}
        result = inventory.measures(client, pull_request=30)
        self.assertEqual(result["values"], {"coverage": "91.2"})
        self.assertEqual(result["period_values"], {"new_coverage": "79.5"})
        self.assertIn("new_uncovered_lines", result["missing_metrics"])
        self.assertNotIn("new_coverage", result["missing_metrics"])

    def test_pr_listing_and_gate_disagreement_rejects_mixed_snapshot(self):
        client = FakeSonar()
        original = client.get
        def inconsistent_gate(endpoint, parameters):
            result = original(endpoint, parameters)
            if endpoint == "qualitygates/project_status":
                result["projectStatus"]["status"] = "ERROR"
            return result
        with patch.object(client, "get", side_effect=inconsistent_gate):
            with self.assertRaisesRegex(inventory.InventoryError, "listing and quality gate disagree"):
                inventory.collect(client, pull_request=30, expected_revision="a" * 40)

    def test_legacy_periods_preserve_indices_and_metric_only_null_values_are_unavailable(self):
        client = MagicMock()
        client.get.return_value = {"component": {"key": inventory.PROJECT, "measures": [
            {"metric": "coverage"}, {"metric": "line_coverage", "value": None},
            {"metric": "branch_coverage", "value": "", "period": None, "periods": []},
            {"metric": "new_coverage", "periods": [{"index": 1, "value": "79.5", "private": "never export"}]},
            {"metric": "new_line_coverage", "periods": [{"index": 1, "value": "0"}, {"index": 2, "value": "55"}]},
            {"metric": "new_uncovered_lines", "periods": [{"index": 1, "value": None}]},
        ]}}
        report = inventory.measures(client, pull_request=30)
        self.assertEqual(report["values"], {})
        self.assertEqual(report["period_values"], {"new_coverage": "79.5"})
        self.assertEqual(report["periods"]["new_line_coverage"], [{"index": 1, "value": "0"}, {"index": 2, "value": "55"}])
        self.assertEqual(report["unavailable_metrics"], ["coverage", "line_coverage", "branch_coverage", "new_uncovered_lines"])
        self.assertIn("new_conditions_to_cover", report["missing_metrics"])
        self.assertNotIn("coverage", report["missing_metrics"])
        self.assertNotIn("never export", json.dumps(report))

    def test_missing_all_measures_preserves_unavailable_not_zero_semantics(self):
        client = MagicMock()
        for source in ({"key": inventory.PROJECT}, {"key": inventory.PROJECT, "measures": None}):
            client.get.return_value = {"component": source}
            report = inventory.measures(client)
            self.assertEqual(report["values"], {})
            self.assertEqual(report["missing_metrics"], list(inventory.METRICS))

    def test_period_bounds_duplicates_and_malformed_values_remain_fail_closed(self):
        values = ([{"index": 1, "value": "1"}] * 2,
                  [{"index": index + 1, "value": "1"} for index in range(inventory.MAX_METRIC_PERIODS + 1)],
                  [{"index": True, "value": "1"}], [{"value": {"private": "not a measurement"}}])
        for value in values:
            with self.subTest(value=value), self.assertRaises(inventory.InventoryError):
                inventory._metric_periods(value)

    def test_missing_metric_values_do_not_discard_pr_issues_or_failed_gate(self):
        client = FakeSonar()
        client.pull_request["status"]["qualityGateStatus"] = "ERROR"
        original = client.get
        def metric_only(endpoint, parameters):
            result = original(endpoint, parameters)
            if endpoint == "measures/component":
                result["component"]["measures"] = [
                    {"metric": "coverage", "value": None},
                    {"metric": "new_coverage", "periods": [{"index": 1, "value": "85"}]},
                ]
            if endpoint == "qualitygates/project_status":
                result["projectStatus"]["status"] = "ERROR"
            return result
        with patch.object(client, "get", side_effect=metric_only):
            report = inventory.collect(client, pull_request=30, expected_revision="a" * 40)
        self.assertEqual(report["issue_count"], 3)
        self.assertEqual(report["quality_gate"]["status"], "ERROR")
        self.assertEqual(report["measures"]["unavailable_metrics"], ["coverage"])
        self.assertEqual(report["measures"]["period_values"], {"new_coverage": "85"})

    def test_scanner_receipt_is_bounded_and_exports_only_validated_task_identifier(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report-task.txt"
            good = f"projectKey={inventory.PROJECT}\nserverUrl={inventory.HOST}\nceTaskId=task_123-ABC\n"
            path.write_text(good + "dashboardUrl=https://private.example/synthetic-secret\nsonar.token=synthetic-secret\n")
            result = inventory.collect(FakeSonar(), pull_request=30, expected_revision="a" * 40, scanner_report=path)
            self.assertEqual(result["scanner_submission"]["ce_task_id"], "task_123-ABC")
            self.assertNotIn("synthetic-secret", json.dumps(result))
            invalid = [good.replace(inventory.PROJECT, "foreign-project"),
                       good + "ceTaskId=duplicate\n", good.replace("task_123-ABC", "bad token"),
                       good.replace(inventory.HOST, "https://attacker.example"), "x" * 32769]
            for content in invalid:
                path.write_text(content)
                with self.subTest(content=content[:25]), self.assertRaises(inventory.InventoryError):
                    inventory.scanner_submission(path)

    def test_pr_cli_publishes_sanitized_gate_failure_without_faking_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "sonar-pr.json"
            client = FakeSonar()
            client.pull_request["status"]["qualityGateStatus"] = "ERROR"
            original = client.get
            def failed_gate(endpoint, parameters):
                result = original(endpoint, parameters)
                if endpoint == "qualitygates/project_status":
                    result["projectStatus"]["status"] = "ERROR"
                return result
            with patch.object(client, "get", side_effect=failed_gate), \
                    patch.object(inventory, "PR_OUTPUT", output), \
                    patch.dict(os.environ, {"SONAR_TOKEN": "synthetic-token"}), \
                    patch.object(inventory, "SonarClient", return_value=client), patch("sys.stdout", new=StringIO()):
                self.assertEqual(inventory.main(["--pull-request", "30", "--expected-revision", "a" * 40]), 0)
            report = json.loads(output.read_text())
            self.assertEqual(report["quality_gate"]["status"], "ERROR")
            self.assertFalse(report["scan_context"]["server_revision_verified"])

    def test_complete_pagination_projects_only_review_fields_and_main_scope(self):
        client = FakeSonar()
        with patch.object(inventory, "PAGE_SIZE", 2):
            report = inventory.collect(client)
        self.assertEqual(report["issue_count"], 3)
        self.assertEqual([row["key"] for row in report["issues"]], ["one", "two", "three"])
        serialized = json.dumps(report)
        for private in ("private@example.test", "private-user", "Private discussion", "private source snippet", "Private event"):
            self.assertNotIn(private, serialized)
        self.assertEqual(report["analysis"]["revision"], "a" * 40)
        self.assertEqual(report["measures"]["values"], {"coverage": "88.9"})
        self.assertIn("line_coverage", report["measures"]["missing_metrics"])
        for endpoint, parameters in client.requests:
            self.assertIn(endpoint, inventory.ENDPOINTS)
            self.assertEqual(parameters["branch"], "main")
        pages = [parameters["p"] for endpoint, parameters in client.requests if endpoint == "issues/search"]
        self.assertEqual(pages, [1, 2])

    def test_empty_inventory_still_requires_existing_project_analysis(self):
        client = FakeSonar()
        client.rows = []
        self.assertEqual(inventory.collect(client)["issue_count"], 0)
        with patch.object(client, "get", return_value={"analyses": []}):
            with self.assertRaises(inventory.InventoryError):
                inventory.collect(client)

    def test_free_text_diagnostics_never_enter_inventory_or_artifact(self):
        private_values = ("person@example.test", "Synthetic Person Name",
                          "synthetic-api-key-unrelated-to-sonar-token",
                          "password = 'synthetic-source-literal'", "Private diagnostic note")
        client = FakeSonar()
        client.rows = []
        for index, private in enumerate(private_values):
            row = sample_issue(str(index))
            row["message"] = private
            row["flows"][0]["locations"][0]["msg"] = private
            client.rows.append(row)
        report = inventory.collect(client)
        for private in private_values:
            self.assertNotIn(private, json.dumps(report))
        for row in report["issues"]:
            self.assertNotIn("message", row)
            self.assertEqual(row["rule"], "python:S0000")
            self.assertEqual(row["component"], inventory.PROJECT + ":src/example.py")
            self.assertEqual(row["line"], 4)
            self.assertEqual(row["flows"][0]["locations"], [{
                "component": inventory.PROJECT + ":src/example.py",
                "textRange": {"startLine": 4, "endLine": 5}}])
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "inventory.json"
            inventory.publish(report, "different-synthetic-sonar-token", output)
            for private in private_values:
                self.assertNotIn(private, output.read_text())

    def test_partial_duplicate_changed_and_oversized_pages_are_rejected(self):
        mutations = (
            lambda response: response["issues"].pop(),
            lambda response: response["issues"].__setitem__(0, sample_issue("one")),
            lambda response: response["paging"].__setitem__("total", 4),
            lambda response: response["paging"].__setitem__("total", inventory.MAX_ISSUES + 1),
            lambda response: response["paging"].__setitem__("pageIndex", 1),
            lambda response: response["paging"].__setitem__("pageSize", True),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                client = FakeSonar()
                original_get = client.get
                def get(endpoint, parameters):
                    response = original_get(endpoint, parameters)
                    if endpoint == "issues/search" and parameters["p"] == 2:
                        mutate(response)
                    return response
                with patch.object(client, "get", side_effect=get), patch.object(inventory, "PAGE_SIZE", 2):
                    with self.assertRaises(inventory.InventoryError):
                        inventory.collect(client)

    def test_foreign_projects_and_malformed_issue_schemas_are_rejected(self):
        for field, value in (("project", "other"), ("component", "other:file.py"),
                             ("key", None), ("line", True), ("flows", {})):
            with self.subTest(field=field):
                row = sample_issue("one")
                row[field] = value
                with self.assertRaises(inventory.InventoryError):
                    inventory.issue(row)

    def test_analysis_revision_change_rejects_mixed_snapshot(self):
        client = FakeSonar()
        original_get = client.get
        def get(endpoint, parameters):
            if endpoint == "qualitygates/project_status":
                client.analysis["revision"] = "b" * 40
            return original_get(endpoint, parameters)
        with patch.object(client, "get", side_effect=get):
            with self.assertRaisesRegex(inventory.InventoryError, "changed during collection"):
                inventory.collect(client)

    def test_mqr_fields_and_optional_locations_preserve_positions(self):
        row = sample_issue("one")
        for key in ("status", "type", "severity", "line"):
            row.pop(key)
        row.update({"issueStatus": "OPEN", "impacts": [{"softwareQuality": "SECURITY", "severity": "HIGH"}],
                    "textRange": {"startLine": 4, "endLine": 5},
                    "flows": [{"locations": [{"msg": "Project-level diagnostic"}]}]})
        result = inventory.issue(row)
        self.assertEqual(result["impacts"], [{"softwareQuality": "SECURITY", "severity": "HIGH"}])
        self.assertEqual(result["textRange"], {"startLine": 4, "endLine": 5})
        self.assertEqual(result["flows"][0]["locations"], [{}])
        row.pop("issueStatus")
        with self.assertRaises(inventory.InventoryError):
            inventory.issue(row)

    def test_measure_project_and_metric_mismatches_are_rejected(self):
        sources = ({"key": "other-project", "measures": []},
                   {"key": inventory.PROJECT, "measures": [{"metric": "other-metric", "value": "1"}]},
                   {"key": inventory.PROJECT, "measures": [{"metric": "coverage", "value": "1"}] * 2})
        for source in sources:
            with self.subTest(source=source):
                client = MagicMock()
                client.get.return_value = {"component": source}
                with self.assertRaises(inventory.InventoryError):
                    inventory.measures(client)

    def test_quality_gate_conditions_and_analysis_revision_are_explicit(self):
        client = MagicMock()
        condition = {"status": "ERROR", "metricKey": "new_coverage", "actualValue": "72.0",
                     "comparator": "LT", "errorThreshold": "80", "privateField": "excluded"}
        client.get.return_value = {"projectStatus": {"status": "ERROR", "conditions": [condition]}}
        gate = inventory.quality_gate(client)
        self.assertEqual(gate["status"], "ERROR")
        self.assertEqual(gate["conditions"][0]["actualValue"], "72.0")
        self.assertNotIn("privateField", gate["conditions"][0])
        client.get.return_value = {"analyses": [{"key": "key", "date": "2026-11-01", "revision": "short"}]}
        with self.assertRaises(inventory.InventoryError):
            inventory.latest_analysis(client)

    def test_client_uses_only_fixed_https_host_get_and_authorization_header(self):
        client = inventory.SonarClient("synthetic-token")
        response = MagicMock()
        response.status = 200
        response.read.return_value = b'{"ok": true}'
        def open_request(request, timeout):
            self.assertTrue(request.full_url.startswith("https://sonarcloud.io/api/issues/search?"))
            self.assertEqual(request.method, "GET")
            self.assertEqual(request.get_header("Authorization"), "Bearer synthetic-token")
            self.assertNotIn("synthetic-token", request.full_url)
            self.assertEqual(timeout, 30)
            response.geturl.return_value = request.full_url
            response.__enter__.return_value = response
            return response
        with patch.object(client.opener, "open", side_effect=open_request):
            self.assertEqual(client.get("issues/search", {"componentKeys": inventory.PROJECT}), {"ok": True})
        with patch.object(client.opener, "open") as opened:
            with self.assertRaises(inventory.InventoryError):
                client.get("https://other.example/api", {})
            opened.assert_not_called()

    def test_http_network_and_redirect_errors_never_include_response_or_token(self):
        client = inventory.SonarClient("synthetic-token")
        errors = [HTTPError(inventory.HOST, 403, "synthetic-token", {}, BytesIO(b"private response")),
                  URLError("private response synthetic-token")]
        for error in errors:
            with self.subTest(error=type(error).__name__), patch.object(client.opener, "open", side_effect=error):
                with self.assertRaises(inventory.InventoryError) as caught:
                    client.get("issues/search", {})
                self.assertNotIn("synthetic-token", str(caught.exception))
                self.assertNotIn("private response", str(caught.exception))
        redirects = inventory.NoRedirects()
        with self.assertRaises(inventory.InventoryError):
            redirects.redirect_request(None, None, 302, "", {}, "https://other.example/")

    def test_bad_or_oversized_http_json_is_rejected(self):
        client = inventory.SonarClient("synthetic-token")
        for payload in (b"not json", b"[]", b"x" * (inventory.MAX_RESPONSE_BYTES + 1)):
            response = MagicMock()
            response.status = 200
            response.geturl.return_value = inventory.HOST + "/api/issues/search?"
            response.read.return_value = payload
            response.__enter__.return_value = response
            with patch.object(client.opener, "open", return_value=response):
                with self.assertRaises(inventory.InventoryError):
                    client.get("issues/search", {})

    def test_publish_redacts_echoed_token_and_never_replaces_existing_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "inventory.json"
            inventory.publish({"message": "synthetic-token"}, "synthetic-token", output)
            self.assertEqual(json.loads(output.read_text()), {"message": "[REDACTED]"})
            with self.assertRaises(FileExistsError):
                inventory.publish({"message": "replace"}, "synthetic-token", output)
            self.assertEqual(json.loads(output.read_text()), {"message": "[REDACTED]"})
            self.assertEqual(list(output.parent.glob("*.tmp")), [])

    def test_missing_secret_and_failed_collection_publish_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "inventory.json"
            with patch.object(inventory, "OUTPUT", output), patch.dict(os.environ, {"SONAR_TOKEN": ""}), \
                    patch.object(inventory, "collect") as collect, patch("sys.stderr", new=StringIO()):
                self.assertEqual(inventory.main([]), 1)
                collect.assert_not_called()
            with patch.object(inventory, "OUTPUT", output), patch.dict(os.environ, {"SONAR_TOKEN": "synthetic-token"}), \
                    patch.object(inventory, "collect", side_effect=inventory.InventoryError("Synthetic failure")), \
                    patch("sys.stderr", new=StringIO()):
                self.assertEqual(inventory.main([]), 1)
            self.assertFalse(output.exists())

    def test_main_publishes_complete_inventory_and_rejects_replacement_before_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "inventory.json"
            with patch.object(inventory, "OUTPUT", output), patch.dict(os.environ, {"SONAR_TOKEN": "synthetic-token"}), \
                    patch.object(inventory, "SonarClient", return_value=FakeSonar()) as client, \
                    patch("sys.stdout", new=StringIO()), patch("sys.stderr", new=StringIO()):
                self.assertEqual(inventory.main([]), 0)
                report = json.loads(output.read_text())
                self.assertEqual(report["issue_count"], 3)
                self.assertEqual(inventory.main([]), 1)
                client.assert_called_once_with("synthetic-token")
            self.assertEqual(json.loads(output.read_text()), report)

    def test_failed_publication_reports_failure_without_a_completed_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "inventory.json"
            with patch.object(inventory, "OUTPUT", output), patch.dict(os.environ, {"SONAR_TOKEN": "synthetic-token"}), \
                    patch.object(inventory, "SonarClient", return_value=FakeSonar()), \
                    patch.object(inventory.os, "fsync", side_effect=OSError("Synthetic storage failure")), \
                    patch("sys.stderr", new=StringIO()) as error:
                self.assertEqual(inventory.main([]), 1)
            self.assertIn("could not be published", error.getvalue())
            self.assertFalse(output.exists())
            self.assertEqual(list(output.parent.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
