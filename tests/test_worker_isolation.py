"""Regression checks for the marker probe. Only the real CLI case exercises the OS boundary."""
from contextlib import redirect_stdout
import errno
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import runpy
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_worker_isolation.py"
SPEC = importlib.util.spec_from_file_location("worker_isolation", SCRIPT)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)

NAMES = ("mnt", "pid", "net", "user")
PARENT = {name: f"{name}:[{100 + index}]" for index, name in enumerate(NAMES)}
CAPS = ("CapPrm", "CapEff", "CapInh", "CapAmb")
INPUT = b"synthetic input"


def synthetic_child():
    return {
        "namespaces": {name: f"{name}:[{200 + index}]" for index, name in enumerate(NAMES)},
        "interfaces": ["lo"], "parent_connect": "ENETUNREACH",
        "private_read": "ENOENT", "private_write": "ENOENT",
        "input_read": "allowed", "input_observed_hex": INPUT.hex(), "input_write": "EROFS", "output_write": "allowed",
        "environment_keys": ["LC_ALL", "PWD"], "environment_is_fixed": True,
        "no_new_privs": 1, "capabilities": {**dict.fromkeys(CAPS, "0"), "CapBnd": "ff"},
    }


def classify(child, private_preserved=True, input_preserved=True, output_matches=True):
    return probe.classify(PARENT, child, private_preserved, input_preserved, output_matches, INPUT.hex())


def invoke_main(*arguments):
    output = io.StringIO()
    with patch.object(sys, "argv", [str(SCRIPT), *arguments]), redirect_stdout(output):
        code = probe.main()
    return code, json.loads(output.getvalue())


class ObservationTests(unittest.TestCase):
    def test_distinct_controls_detect_each_unexpected_observation(self):
        cases = [
            ("only_loopback_interface", {"interfaces": ["lo", "eth0"]}),
            ("parent_tcp_unreachable", {"parent_connect": "connected"}),
            ("parent_tcp_unreachable", {"parent_connect": "EPERM"}),
            ("parent_tcp_unreachable", {"parent_connect": "ETIMEDOUT"}),
            ("private_absent_for_read_and_write", {"private_read": "allowed"}),
            ("private_absent_for_read_and_write", {"private_write": "allowed"}),
            ("private_absent_for_read_and_write", {"private_read": "EACCES", "private_write": "EACCES"}),
            ("input_read_only", {"input_write": "allowed"}),
            ("input_read_only", {"input_read": "EACCES"}),
            ("input_read_only", {"input_observed_hex": b"wrong marker".hex()}),
            ("writable_output_returned", {"output_write": "EROFS"}),
            ("only_fixed_environment", {"environment_keys": ["LC_ALL", probe.MARKER]}),
            ("only_fixed_environment", {"environment_is_fixed": False}),
            ("no_new_privileges", {"no_new_privs": 0}),
        ]
        for name in NAMES:
            cases.append(("distinct_namespaces", {"namespaces": {**synthetic_child()["namespaces"], name: PARENT[name]}}))
        for cap in CAPS:
            cases.append(("no_permitted_effective_inheritable_or_ambient_caps",
                          {"capabilities": {**synthetic_child()["capabilities"], cap: "01"}}))
        for failed, change in cases:
            with self.subTest(change=change):
                checks = classify({**synthetic_child(), **change})
                self.assertEqual({key for key, passed in checks.items() if not passed}, {failed})

    def test_parent_file_comparisons_are_independent_of_child_reports(self):
        for failed, comparisons in [
            ("parent_marker_preserved", (False, True, True)),
            ("input_read_only", (True, False, True)),
            ("writable_output_returned", (True, True, False)),
        ]:
            with self.subTest(failed=failed):
                checks = classify(synthetic_child(), *comparisons)
                self.assertEqual({key for key, passed in checks.items() if not passed}, {failed})
        for code in ("ENETUNREACH", "EHOSTUNREACH", "ECONNREFUSED"):
            child = {**synthetic_child(), "parent_connect": code}
            self.assertTrue(all(classify(child).values()))

    def test_child_opens_only_virtual_markers_and_connects_to_the_supplied_loopback_port(self):
        # No fallback to builtins.open or a real socket is available in this test.
        private = "/synthetic/parent-only"

        def virtual_open(path, mode="r", **kwargs):
            if path == private and mode in ("rb", "r+b"):
                if scenario == "exposed":
                    return io.BytesIO(b"private synthetic marker")
                raise FileNotFoundError(errno.ENOENT, "absent")
            if (path, mode) == ("/fixture/input", "rb"):
                if scenario == "denied input":
                    raise PermissionError(errno.EACCES, "fixture read denied")
                return io.BytesIO(INPUT)
            if (path, mode) == ("/fixture/input", "ab"):
                if scenario == "exposed":
                    return io.BytesIO()
                raise OSError(errno.EROFS, "read only")
            if (path, mode) == ("/fixture/output", "wb"):
                if scenario == "denied output":
                    raise PermissionError(errno.EACCES, "fixture write denied")
                return output
            if (path, mode) == ("/proc/net/dev", "r"):
                return io.StringIO("lo: 0 0\n")
            if (path, mode) == ("/proc/self/status", "r"):
                return io.StringIO("NoNewPrivs: 1\n" + "".join(f"{cap}: 0\n" for cap in (*CAPS, "CapBnd")))
            self.fail(f"Unexpected file access {(path, mode)}")

        for scenario, failed in [
            ("regular", set()),
            ("exposed", {"private_absent_for_read_and_write", "input_read_only", "parent_tcp_unreachable"}),
            ("denied input", {"input_read_only"}),
            ("denied output", {"writable_output_returned"}),
        ]:
            output = MagicMock()
            with (
                self.subTest(scenario=scenario),
                patch("builtins.open", side_effect=virtual_open) as opened,
                patch.object(probe.socket, "socket") as socket_factory,
                patch.object(probe, "namespace_ids", return_value=synthetic_child()["namespaces"]),
                patch.dict(os.environ, {"LC_ALL": "C"}, clear=True),
            ):
                endpoint = socket_factory.return_value.__enter__.return_value
                if scenario != "exposed":
                    endpoint.connect.side_effect = OSError(errno.ENETUNREACH, "unreachable")
                observed = probe.child_observations({"port": 43210, "private": private})
                endpoint.connect.assert_called_once_with(("127.0.0.1", 43210))
                opened.assert_any_call(private, "r+b")
                if scenario == "denied input":
                    self.assertEqual((observed["input_read"], observed["input_observed_hex"]), ("EACCES", None))
                elif scenario == "denied output":
                    self.assertEqual(observed["output_write"], "EACCES")
                else:
                    output.__enter__.return_value.write.assert_called_once_with(b"child:" + INPUT)
                self.assertEqual({key for key, passed in classify(observed).items() if not passed}, failed)

    def test_wrong_nonce_from_owned_address_cannot_pass_as_positive_control(self):
        address = ("127.0.0.1", 43210)
        with patch.object(probe.socket, "create_connection") as connect:
            connection = connect.return_value.__enter__.return_value
            reader = connection.makefile.return_value.__enter__.return_value
            reader.readline.return_value = b"wrong echo\n"
            with self.assertRaisesRegex(ValueError, "wrong nonce"):
                probe.host_tcp_control(address, "before child")
        connect.assert_called_once_with(address, timeout=1)
        self.assertNotEqual(connection.sendall.call_args.args[0], reader.readline.return_value)

    def test_runtime_mounts_select_read_only_runtime_and_distinct_absolute_libraries(self):
        fake_ldd = "relative.so => missing\nsynthetic.so => /synthetic/lib.so (0x0)\n"
        discovered = json.dumps(["/synthetic/stdlib", ["/synthetic/extension.so"]])
        with (
            patch.object(probe, "system_output", side_effect=[discovered, fake_ldd, fake_ldd]),
            patch.object(probe, "RUNTIME", sys.executable),
        ):
            executable, mounts = probe.runtime_mounts()
        self.assertEqual(mounts, ["--ro-bind", executable, executable,
                                  "--ro-bind", "/synthetic/stdlib", "/synthetic/stdlib",
                                  "--ro-bind", "/synthetic/lib.so", "/synthetic/lib.so"])


class ProbeOutcomeTests(unittest.TestCase):
    def test_cli_rejects_arguments_and_fingerprints_source_before_launch(self):
        with patch.object(probe, "run_probe") as run:
            code, report = invoke_main("--arbitrary-target")
        run.assert_not_called()
        self.assertEqual((code, report["status"]), (2, "inconclusive"))
        self.assertIn("no arguments", report["reason"])
        self.assertEqual(report["probe_sha256"], hashlib.sha256(SCRIPT.read_bytes()).hexdigest())

    def test_missing_platform_and_timeout_are_inconclusive(self):
        with patch.object(probe.platform, "system", return_value="NonLinux"):
            code, report = invoke_main()
        self.assertEqual((code, report["status"]), (2, "inconclusive"))
        self.assertIn("Linux namespace", report["reason"])
        with patch.object(probe, "run_probe", side_effect=subprocess.TimeoutExpired(["synthetic"], 1)):
            code, report = invoke_main()
        self.assertEqual((code, report["status"]), (2, "inconclusive"))
        self.assertIn("timed out", report["reason"])

    @unittest.skipUnless(platform.system() == "Linux", "Harness uses Linux procfs and a disposable /tmp directory")
    def test_cli_distinguishes_missing_controls_from_observed_child_failure(self):
        good = subprocess.CompletedProcess([], 0, json.dumps(synthetic_child()), "")
        incomplete = synthetic_child()
        del incomplete["namespaces"]["net"]
        unreadable = {**synthetic_child(), "input_read": "EACCES", "input_observed_hex": None}
        unwritable = {**synthetic_child(), "output_write": "EROFS"}
        read_bytes = Path.read_bytes

        def fixture_read(path):
            if scenario == "invalid host file" and path.name == "parent-only":
                return b"unexpected synthetic marker"
            return read_bytes(path)

        for scenario, controls, child_result, expected, detail in [
            ("missing launcher", (True, True), subprocess.CompletedProcess([], 1, "", "permission denied"),
             (2, "inconclusive"), "Fixed child unavailable"),
            ("incomplete report", (True, True), subprocess.CompletedProcess([], 0, json.dumps(incomplete), ""),
             (2, "inconclusive"), "net"),
            ("invalid before echo", (False, True), good, (2, "inconclusive"), "before child"),
            ("missing after echo", (True, OSError("no listener")), good, (2, "inconclusive"), "after child"),
            ("invalid host file", (True, True), good, (2, "inconclusive"), "read back"),
            ("no returned output", (True, True), good, (1, "failed"), {"writable_output_returned"}),
            ("denied input", (True, True), subprocess.CompletedProcess([], 0, json.dumps(unreadable), ""),
             (1, "failed"), {"input_read_only", "writable_output_returned"}),
            ("denied output", (True, True), subprocess.CompletedProcess([], 0, json.dumps(unwritable), ""),
             (1, "failed"), {"writable_output_returned"}),
        ]:
            with (
                self.subTest(scenario=scenario),
                patch.object(probe, "system_output", return_value="synthetic version"),
                patch.object(probe, "runtime_mounts", return_value=(probe.RUNTIME, [])),
                patch.object(probe.secrets, "token_bytes", side_effect=[b"private synthetic marker", INPUT, b"environment"]),
                patch.object(Path, "read_bytes", fixture_read),
                patch.object(probe.socketserver, "TCPServer") as server,
                patch.object(probe, "round_trip", side_effect=controls),
                patch.object(probe.subprocess, "run", return_value=child_result) as launcher,
            ):
                listener = server.return_value.__enter__.return_value
                listener.server_address = ("127.0.0.1", 43210)
                code, report = invoke_main()
                self.assertEqual((code, report["status"]), expected)
                server.assert_called_once_with(("127.0.0.1", 0), probe.Echo)
                if expected[0] == 2:
                    self.assertIn(detail, report["reason"])
                else:
                    self.assertEqual({key for key, passed in report["checks"].items() if not passed}, detail)
                if scenario in {"invalid before echo", "invalid host file"}:
                    launcher.assert_not_called()

    @unittest.skipUnless(platform.system() == "Linux", "A real worker boundary requires Linux namespaces")
    def test_real_cli_worker_observations_when_linux_allows_namespace_creation(self):
        if os.path.lexists("/fixture"):
            self.skipTest("Reserved fixture path already exists on the host")
        env = {"LC_ALL": "C"}
        output = io.StringIO()
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(sys, "argv", [str(SCRIPT)]),
            redirect_stdout(output),
            self.assertRaises(SystemExit) as exited,
        ):
            runpy.run_path(str(SCRIPT), run_name="__main__")
        report = json.loads(output.getvalue())
        if (exited.exception.code, report["status"]) == (2, "inconclusive"):
            missing = [path for path in (probe.BWRAP, probe.UNSHARE, probe.RUNTIME, "/usr/bin/ldd")
                       if not os.access(path, os.X_OK)]
            if missing:
                self.skipTest(f"Fixed Linux runtime tools unavailable: {missing}; {report['reason']}")
            prerequisite = subprocess.run(
                [probe.UNSHARE, "--user", "--map-root-user", "--net", "--mount", "--pid", "--fork", "--", "/usr/bin/true"],
                env=env, capture_output=True, text=True, timeout=5)
            if prerequisite.returncode and "Operation not permitted" in prerequisite.stderr and "permitted" in report["reason"]:
                self.skipTest("Host policy independently denied namespace creation: " + prerequisite.stderr.strip())
        self.assertEqual((exited.exception.code, report["status"]), (0, "passed"), report)
        self.assertTrue(report["checks"]["host_tcp_nonce_before"])
        self.assertTrue(report["checks"]["host_tcp_nonce_after"])
        self.assertTrue(all(report["checks"].values()), report)
        child = report["child"]
        for name in NAMES:
            self.assertNotEqual(report["parent_namespaces"][name], child["namespaces"][name], name)
        self.assertEqual(child["interfaces"], ["lo"])
        self.assertIn(child["parent_connect"], {"ENETUNREACH", "EHOSTUNREACH", "ECONNREFUSED"})
        self.assertEqual((child["private_read"], child["private_write"], child["input_write"]),
                         ("ENOENT", "ENOENT", "EROFS"))
        observed_input = bytes.fromhex(child["input_observed_hex"])
        self.assertEqual(hashlib.sha256(observed_input).hexdigest(), report["fixture_input_sha256"])
        self.assertEqual((child["input_read"], child["output_write"]), ("allowed", "allowed"))
        self.assertNotIn(probe.MARKER, child["environment_keys"])
        self.assertEqual(report["probe_sha256"], hashlib.sha256(SCRIPT.read_bytes()).hexdigest())
