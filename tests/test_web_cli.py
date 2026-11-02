"""The ordinary workbench launcher must preserve its local-only boundary."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from security_lab.web_cli import main


class WebLauncherTests(unittest.TestCase):
    def test_launch_binds_loopback_with_one_worker_and_requested_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frontend = root / "frontend"
            frontend.mkdir()
            (frontend / "index.html").write_text("<html></html>", encoding="utf-8")
            workspace, cases = root / "evidence", root / "cases"
            with patch("security_lab.server.create_app") as create, \
                    patch("uvicorn.run") as serve, redirect_stdout(StringIO()):
                result = main(["--workspace", str(workspace), "--cases", str(cases),
                               "--frontend-dir", str(frontend), "--port", "9123"])
            self.assertEqual(result, 0)
            create.assert_called_once_with(workspace, cases, frontend)
            serve.assert_called_once_with(create.return_value, host="127.0.0.1", port=9123,
                                          workers=1, reload=False, access_log=False)

    def test_missing_frontend_never_creates_workspace_or_starts_server(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("security_lab.server.create_app") as create, \
                    patch("uvicorn.run") as serve, redirect_stderr(StringIO()) as error:
                with self.assertRaises(SystemExit) as stopped:
                    main(["--frontend-dir", directory])
            self.assertEqual(stopped.exception.code, 2)
            self.assertIn("React-Build fehlt", error.getvalue())
            create.assert_not_called()
            serve.assert_not_called()

    def test_invalid_ports_fail_before_application_creation(self):
        for port in ("0", "1023", "65536", "not-a-port"):
            with self.subTest(port=port), patch("security_lab.server.create_app") as create, \
                    patch("uvicorn.run") as serve, redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as stopped:
                    main(["--port", port])
                self.assertEqual(stopped.exception.code, 2)
                create.assert_not_called()
                serve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
