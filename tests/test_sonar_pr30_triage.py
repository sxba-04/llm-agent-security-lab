"""Offline operation-boundary tests; never use a real Sonar token or network."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("triage", ROOT / "scripts/sonar_pr30_triage.py")
triage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(triage)
STAMP = "2026-11-06T10:30:00+0000"


class FakeClient:
    def __init__(self):
        self.posts = []
        self.date = STAMP
        self.rows = {key: {"key": key, "project": triage.PROJECT,
                          "component": triage.PROJECT + ":" + path,
                          "rule": "python:S0000", "status": "OPEN", "transitions": ["falsepositive"],
                          "message": "SECRET_UPSTREAM_MESSAGE", "comments": [{"markdown": "SECRET_COMMENT"}],
                          "flows": [{"locations": [{"component": triage.PROJECT + ":" + path,
                                                    "textRange": {"startLine": 1, "endLine": 2},
                                                    "msg": "SECRET_FLOW_MESSAGE"}]}]}
                     for key, path in triage.KNOWN.items()}
        self.fail_comment = False
        self.fail_transition = False

    def request(self, endpoint, parameters, *, post=False):
        if post:
            self.posts.append((endpoint, copy.deepcopy(parameters)))
            key = parameters["issue"]
            if endpoint == "issues/add_comment" and self.fail_comment:
                raise triage.SafeError("Comment failed.")
            if endpoint == "issues/do_transition":
                if self.fail_transition:
                    raise triage.SafeError("Transition failed.")
                self.rows[key].update(status="RESOLVED", resolution="FALSE-POSITIVE", transitions=[])
            return {"issue": {"key": key}}
        if endpoint == "project_pull_requests/list":
            return {"pullRequests": [{"key": "30", "analysisDate": self.date}]}
        assert endpoint == "issues/search"
        assert parameters["componentKeys"] == triage.PROJECT
        assert parameters["pullRequest"] == "30"
        assert parameters["additionalFields"] == "transitions"
        keys = parameters.get("issues", ",".join(self.rows)).split(",")
        rows = [copy.deepcopy(self.rows[k]) for k in keys if k in self.rows]
        return {"paging": {"total": len(rows), "pageIndex": parameters["p"], "pageSize": 100}, "issues": rows}


class OperationTests(unittest.TestCase):
    def setUp(self):
        # Any accidental real transport in a test fails before contacting a host.
        self.network = patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("Network forbidden in tests"))
        self.network.start(); self.addCleanup(self.network.stop)
        self.data, self.entries, self.digest = triage.load_allowlist(ROOT / "scripts/sonar_pr30_allowlist.json")
        self.client = FakeClient()

    def approved(self):
        self.data.update(approved=True, expected_analysis_date=STAMP)
        for entry in self.entries.values():
            entry["rule"] = "python:S0000"

    def run_apply(self, report=None):
        with patch.object(triage, "APPROVED_ALLOWLIST_SHA256", self.digest):
            triage.run(self.client, self.data, self.entries, self.digest,
                       report if report is not None else {"mutations": []}, True)

    def test_default_inventory_is_read_only_and_has_no_messages(self):
        report = {"mutations": []}
        triage.run(self.client, self.data, self.entries, self.digest, report)
        self.assertEqual(self.client.posts, [])
        self.assertEqual(len(report["inventory"]), 9)
        self.assertIn("textRange", report["inventory"][0]["flows"][0]["locations"][0])
        self.assertNotIn("SECRET", json.dumps(report))
        self.assertFalse(report["revision_verified_by_server"])

    def test_unapproved_pin_blocks_every_post(self):
        with self.assertRaisesRegex(triage.SafeError, "Apply disabled"):
            triage.run(self.client, self.data, self.entries, self.digest, {"mutations": []}, True)
        self.assertEqual(self.client.posts, [])

    def test_rule_and_missing_issue_fail_before_all_posts(self):
        self.approved()
        key = next(iter(triage.KNOWN))
        for change in ("rule", "missing"):
            with self.subTest(change=change):
                self.client = FakeClient()
                if change == "rule": self.client.rows[key]["rule"] = "python:DIFFERENT"
                else: del self.client.rows[key]
                with self.assertRaises(triage.SafeError): self.run_apply()
                self.assertEqual(self.client.posts, [])

    def test_analysis_pin_and_transition_permission_fail_before_writes(self):
        self.approved(); self.data["expected_analysis_date"] = "other"
        with self.assertRaises(triage.SafeError): self.run_apply()
        self.data["expected_analysis_date"] = STAMP
        next(iter(self.client.rows.values()))["transitions"] = []
        with self.assertRaises(triage.SafeError): self.run_apply()
        self.assertEqual(self.client.posts, [])

    def test_exact_nine_comments_precede_transitions_and_status_is_verified(self):
        self.approved(); report = {"mutations": []}
        self.run_apply(report)
        self.assertEqual(len(self.client.posts), 18)
        for index in range(0, 18, 2):
            comment, transition = self.client.posts[index:index+2]
            self.assertEqual(comment[0], "issues/add_comment")
            self.assertEqual(transition[0], "issues/do_transition")
            self.assertEqual(comment[1]["issue"], transition[1]["issue"])
            self.assertEqual(transition[1]["transition"], "falsepositive")
            self.assertEqual(comment[1]["text"], self.entries[comment[1]["issue"]]["comment"])
        self.assertEqual({r["state"] for r in report["mutations"]}, {"false_positive_verified"})
        self.assertNotIn("SECRET", json.dumps(report))

    def test_already_false_positive_is_idempotent(self):
        self.approved()
        for row in self.client.rows.values(): row.update(status="RESOLVED", resolution="FALSE-POSITIVE", transitions=[])
        self.run_apply()
        self.assertEqual(self.client.posts, [])

    def test_comment_failure_never_transitions_and_partial_receipt_is_clear(self):
        self.approved(); self.client.fail_comment = True; report = {"mutations": []}
        with self.assertRaises(triage.SafeError): self.run_apply(report)
        self.assertEqual([p[0] for p in self.client.posts], ["issues/add_comment"])
        self.assertEqual(report["mutations"][0]["state"], "comment_attempted")

    def test_failed_transition_stops_without_automatic_retry(self):
        self.approved(); self.client.fail_transition = True; report = {"mutations": []}
        with self.assertRaises(triage.SafeError): self.run_apply(report)
        self.assertEqual(len(self.client.posts), 2)
        self.assertEqual(report["mutations"][0]["state"], "transition_attempted")

    def test_foreign_project_or_pr_or_component_fails_closed(self):
        for field, value in (("project", "another"), ("pullRequest", "31"), ("component", "another:file.py")):
            with self.subTest(field=field):
                row = copy.deepcopy(next(iter(self.client.rows.values())))
                row[field] = value
                with self.assertRaises(triage.SafeError): triage.project_issue(row)

    def test_allowlist_cannot_include_oauth_or_unreviewed_ids(self):
        self.data["issues"][0]["key"] = "AaGwHn_y3f6_aqzNEjB3"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "list.json"; path.write_text(json.dumps(self.data))
            with self.assertRaises(triage.SafeError): triage.load_allowlist(path)

    def test_transport_is_fixed_host_form_post_no_redirects_and_bounded(self):
        client = triage.Client("TEST_TOKEN", allow_writes=True)
        key = next(iter(triage.KNOWN)); seen = []
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_args): pass
            def geturl(self): return seen[0][0].full_url
            def read(self, amount):
                self_amount.append(amount)
                return b'{"issue":{"key":"' + key.encode() + b'"}}'
        self_amount = []
        client.opener = Mock()
        client.opener.open.side_effect = lambda request, **kwargs: seen.append((request, kwargs)) or Response()
        client.request("issues/add_comment", {"issue": key, "text": "Evidence & literal + symbols"}, post=True)
        request, options = seen[0]
        self.assertEqual(request.full_url, triage.HOST + "/api/issues/add_comment")
        self.assertEqual(parse_qs(request.data.decode())["text"], ["Evidence & literal + symbols"])
        self.assertEqual(options["timeout"], 20)
        self.assertEqual(self_amount, [triage.MAX_BYTES + 1])
        with self.assertRaises(triage.SafeError): triage.NoRedirects().redirect_request(None,None,302,None,None,"https://other.invalid")

    def test_post_and_endpoint_guards_prevent_other_mutations(self):
        client = triage.Client("TEST_TOKEN")
        with self.assertRaises(triage.SafeError): client.request("issues/add_comment", {}, post=True)
        with self.assertRaises(triage.SafeError): client.request("qualitygates/update", {}, post=True)
        client.allow_writes = True
        with self.assertRaises(triage.SafeError): client.request("issues/do_transition", {"issue": "other", "transition": "falsepositive"}, post=True)
        with self.assertRaises(triage.SafeError): client.request("issues/do_transition", {"issue": next(iter(triage.KNOWN)), "transition": "wontfix"}, post=True)

    def test_http_and_transport_errors_do_not_expose_remote_or_secret_values(self):
        client = triage.Client("TEST_TOKEN"); client.opener = Mock()
        for error in (HTTPError(triage.HOST, 403, "SECRET_REMOTE", {}, io.BytesIO(b"SECRET_BODY")), URLError("SECRET_PROXY")):
            client.opener.open.side_effect = error
            with self.assertRaises(triage.SafeError) as caught: client.request("issues/search", {})
            self.assertNotIn("SECRET", str(caught.exception))

    def test_branch_and_actor_guards(self):
        environment = {"GITHUB_REPOSITORY": triage.REPOSITORY, "GITHUB_REPOSITORY_OWNER": "sxba-04", "GITHUB_ACTOR": "sxba-04", "GITHUB_REF": triage.OPS_REF, "GITHUB_EVENT_NAME": "workflow_dispatch"}
        with patch.dict(triage.os.environ, environment, clear=True): triage.branch_guard()
        for name in environment:
            with patch.dict(triage.os.environ, {**environment, name: "different"}, clear=True):
                with self.assertRaises(triage.SafeError): triage.branch_guard()

    def test_duplicate_json_and_nonfinite_values_fail_closed(self):
        for content in (b'{"key":1,"key":2}', b'{"value":NaN}'):
            with self.assertRaises(triage.SafeError): triage.parse_json(content)

    def test_analysis_changes_after_comment_withhold_transition(self):
        self.approved(); original = self.client.request
        def changed(endpoint, parameters, *, post=False):
            value = original(endpoint, parameters, post=post)
            if endpoint == "issues/add_comment": self.client.date = "2026-11-07T10:30:00+0000"
            return value
        self.client.request = changed
        with self.assertRaises(triage.SafeError): self.run_apply()
        self.assertEqual([p[0] for p in self.client.posts], ["issues/add_comment"])

    def test_successful_http_without_changed_status_is_not_success(self):
        self.approved(); original = self.client.request
        def unchanged(endpoint, parameters, *, post=False):
            value = original(endpoint, parameters, post=post)
            if endpoint == "issues/do_transition": self.client.rows[parameters["issue"]].update(status="OPEN", resolution="UNRESOLVED")
            return value
        self.client.request = unchanged
        with self.assertRaises(triage.SafeError): self.run_apply()
        self.assertEqual(len(self.client.posts), 2)

    def test_duplicate_inventory_row_is_rejected(self):
        original = self.client.request
        def duplicate(endpoint, parameters, *, post=False):
            value = original(endpoint, parameters, post=post)
            if endpoint == "issues/search":
                value["issues"].append(copy.deepcopy(value["issues"][0])); value["paging"]["total"] += 1
            return value
        self.client.request = duplicate
        with self.assertRaises(triage.SafeError): triage.inventory(self.client)

    def test_unexpected_redirect_url_and_oversize_responses_are_rejected(self):
        client = triage.Client("TEST_TOKEN"); client.opener = Mock()
        response = Mock(); response.__enter__ = Mock(return_value=response); response.__exit__ = Mock(return_value=None)
        response.status = 200; response.geturl.return_value = "https://other.invalid/"
        client.opener.open.return_value = response
        with self.assertRaises(triage.SafeError): client.request("issues/search", {})
        response.geturl.return_value = triage.HOST + "/api/issues/search?"
        response.read.return_value = b"x" * (triage.MAX_BYTES + 1)
        with self.assertRaises(triage.SafeError): client.request("issues/search", {})

    def test_existing_receipt_prevents_any_remote_call(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "receipt.json"; output.write_text("original receipt")
            with patch.object(triage, "OUTPUT", output), patch.object(triage, "Client") as client, patch("sys.stderr", io.StringIO()):
                self.assertEqual(triage.main(["--apply"]), 1)
            client.assert_not_called()
            self.assertEqual(output.read_text(), "original receipt")

    def test_final_query_missing_or_reopened_issue_is_not_success(self):
        self.approved()
        for mutation in ("missing", "reopened"):
            with self.subTest(mutation=mutation):
                self.client = FakeClient(); original = self.client.request
                def final_changed(endpoint, parameters, *, post=False):
                    value = original(endpoint, parameters, post=post)
                    if endpoint == "issues/search" and "," in parameters.get("issues", ""):
                        if mutation == "missing":
                            value["issues"].pop(); value["paging"]["total"] -= 1
                        else:
                            value["issues"][0].update(status="OPEN", resolution="UNRESOLVED")
                    return value
                self.client.request = final_changed
                with self.assertRaisesRegex(triage.SafeError, "Final selected"):
                    self.run_apply()

    def test_token_echo_in_allowed_fields_cannot_reach_receipt(self):
        token = "TEST_TOKEN"
        self.client.rows[next(iter(triage.KNOWN))]["rule"] = token
        report = {"mutations": []}
        triage.run(self.client, self.data, self.entries, self.digest, report)
        encoded = json.dumps(triage.redact(report, token))
        self.assertNotIn(token, encoded)
        self.assertIn("[REDACTED]", encoded)
        quoted = 'secret"token'
        self.assertNotIn(quoted, json.dumps(triage.redact({"key": quoted, quoted: [quoted]}, quoted)))


if __name__ == "__main__":
    unittest.main()
