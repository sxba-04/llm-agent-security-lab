"""Read-only setup diagnostics and credential-safe failure messages."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from security_lab import doctor


class DoctorTests(unittest.TestCase):
    def test_missing_workspace_and_build_are_reported_without_creating_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "existing.txt").write_text("unchanged", encoding="utf-8")
            before = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}
            with patch.object(doctor, "version_checks", return_value=[]), patch.dict(os.environ, {}, clear=True):
                report = doctor.diagnose(root, root / "missing" / "workspace", [])
            self.assertFalse(report["ready"])
            self.assertEqual(next(row for row in report["checks"] if row["name"] == "frontend-build")["status"], "error")
            self.assertFalse((root / "missing").exists())
            after = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}
            self.assertEqual(before, after)

    def test_proxy_credentials_and_certificate_paths_are_never_echoed(self):
        values = {"HTTPS_PROXY": "http://secret-user:secret-password@proxy.example:8080",
                  "HTTP_PROXY": "http://secret-user:secret-password@proxy.example:bad-port",
                  "SSL_CERT_FILE": "/private/secret-certificate-path.pem", "NODE_TLS_REJECT_UNAUTHORIZED": "0"}
        encoded = json.dumps(doctor.network_configuration_checks(values))
        for secret in ("secret-user", "secret-password", "proxy.example", "secret-certificate-path"):
            self.assertNotIn(secret, encoded)
        checks = {row["name"]: row for row in doctor.network_configuration_checks(values)}
        self.assertEqual(checks["proxy:HTTPS_PROXY"]["status"], "ok")
        self.assertEqual(checks["proxy:HTTP_PROXY"]["status"], "error")
        self.assertEqual(checks["ca:SSL_CERT_FILE"]["status"], "error")
        self.assertEqual(checks["tls-policy"]["status"], "error")

    def test_occupied_port_warns_without_stopping_listener(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(2)
            port = listener.getsockname()[1]
            self.assertEqual(doctor.port_check(port)["status"], "warning")
            self.assertEqual(listener.getsockname()[1], port)

    def test_stale_build_and_low_disk_space_are_warnings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build = root / "frontend" / "dist" / "index.html"
            build.parent.mkdir(parents=True)
            build.write_text("build", encoding="utf-8")
            source = root / "frontend" / "index.html"
            source.write_text("source", encoding="utf-8")
            os.utime(build, (100, 100))
            os.utime(source, (200, 200))
            self.assertEqual(doctor.build_check(root)["status"], "warning")
            usage = type("DiskUsage", (), {"free": 100 * doctor.MIB, "total": 1024 * doctor.MIB})()
            with patch.object(doctor.shutil, "disk_usage", return_value=usage):
                rows = doctor.workspace_checks(root)
            self.assertEqual(next(row for row in rows if row["name"] == "disk-space")["status"], "warning")

    def test_version_command_output_is_reduced_to_numeric_version(self):
        result = type("Result", (), {"returncode": 0, "stdout": "node secret-password v24.22.1\n"})()
        with patch.object(doctor.shutil, "which", return_value="/tools/node"), \
             patch.object(doctor.subprocess, "run", return_value=result) as execute:
            self.assertEqual(doctor.tool_version("node"), "24.22.1")
        self.assertEqual(execute.call_args.args[0], ["/tools/node", "--version"])

    def test_file_in_workspace_path_is_an_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "file"
            path.write_text("original", encoding="utf-8")
            self.assertEqual(doctor.workspace_checks(path / "child")[0]["status"], "error")
            self.assertEqual(path.read_text(encoding="utf-8"), "original")


if __name__ == "__main__":
    unittest.main()
