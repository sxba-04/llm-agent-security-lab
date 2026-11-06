"""Browser fixtures must not contaminate a research workspace or its backup."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def _fixture(path: str):
    spec = importlib.util.spec_from_file_location("browser_fixture", ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BrowserFixtureIsolationTests(unittest.TestCase):
    def test_local_fixture_does_not_add_unknown_roots_to_default_workspace(self):
        module = _fixture("frontend/e2e/server.py")
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            runs = project / "runs"
            runs.mkdir()
            (runs / "preserve.txt").write_text("research evidence", encoding="utf-8")
            observed = []

            def launch(arguments):
                workspace = Path(arguments[arguments.index("--workspace") + 1])
                self.assertTrue(workspace.is_dir())
                self.assertFalse(workspace.is_relative_to(project))
                (workspace / "synthetic.json").write_text("{}", encoding="utf-8")
                observed.append(workspace)
                return 0

            with patch.object(module, "ROOT", project), patch.object(module, "launch_workbench", side_effect=launch):
                self.assertEqual(module.main(), 0)
            self.assertEqual([p.name for p in runs.iterdir()], ["preserve.txt"])
            self.assertEqual((runs / "preserve.txt").read_text(encoding="utf-8"), "research evidence")
            self.assertFalse(observed[0].exists())

    def test_hosted_fixture_keeps_certificates_and_workspace_outside_research_data(self):
        module = _fixture("frontend/e2e-hosted/server.py")
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            observed = []
            app = SimpleNamespace(state=SimpleNamespace(github_sessions=SimpleNamespace()))

            def create_app(workspace, *_args, **_kwargs):
                self.assertTrue(workspace.parent.is_dir())
                self.assertFalse(workspace.is_relative_to(project))
                workspace.mkdir()
                observed.append(workspace.parent)
                return app

            def serve(_app, **kwargs):
                self.assertEqual(Path(kwargs["ssl_certfile"]).parent, observed[0])
                self.assertEqual(Path(kwargs["ssl_keyfile"]).parent, observed[0])

            with (patch.object(module, "ROOT", project),
                  patch("sys.argv", ["server.py", "api"]),
                  patch.object(module.subprocess, "run"),
                  patch("security_lab.server.create_app", side_effect=create_app),
                  patch("uvicorn.run", side_effect=serve)):
                module.main()
            self.assertFalse((project / "runs").exists())
            self.assertFalse(observed[0].exists())
