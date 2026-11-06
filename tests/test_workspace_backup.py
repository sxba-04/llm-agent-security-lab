import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from security_lab import backup
from security_lab.batch import run_batch
from security_lab.cases import load_cases
from security_lab.documents import load_document
from security_lab.jobs import _worker_lease
from security_lab.models import ScriptedModel
from security_lab.review import export_review
from security_lab.batch import load_results


class WorkspaceBackupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_cases(Path(__file__).parents[1] / "cases/dev")[:1]

    def fixture(self, root):
        source = root / "code"
        source.mkdir()
        for name in backup.SOURCE_LOCKFILES:
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic source fixture\n")
        (source / "main.py").write_text("# frozen source fixture\n")
        for args in (("init", "-q"), ("add", "."), ("-c", "user.name=Backup Test", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture")):
            subprocess.run(["git", *args], cwd=source, check=True, capture_output=True)
        workspace = root / "workspace"
        campaign = workspace / "campaigns" / "campaign-fixture"
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
        provenance = {"git_commit": commit, "git_status": "", "source_sha256": {
            "main.py": hashlib.sha256((source / "main.py").read_bytes()).hexdigest()}}
        with patch("security_lab.batch.provenance", return_value=provenance):
            run_batch(self.cases, campaign, ScriptedModel, variants=["B"], sources=["clean"])
        export_review(load_results(campaign), campaign / "reviews" / "review-fixture")
        document_id = "doc-" + "a" * 32
        document = workspace / "documents" / document_id
        document.mkdir(parents=True)
        original, text = b"%PDF-synthetic-original", b"unassigned source fixture"
        (document / "original.pdf").write_bytes(original)
        (document / "extracted.txt").write_bytes(text)
        (document / "document.json").write_text(json.dumps({"document_id": document_id,
            "filename": "unassigned.pdf", "origin": "uploaded_pdf", "page_count": 1,
            "extractor": "synthetic-test-fixture", "sha256": hashlib.sha256(original).hexdigest(),
            "text_sha256": hashlib.sha256(text).hexdigest()}))
        (workspace / "workers").mkdir()
        (workspace / "workers" / "retired.lock").write_text("0")
        (workspace / "exports").mkdir()
        (workspace / "exports" / "cache.zip").write_bytes(b"regenerable cache")
        return workspace, source, campaign, document_id

    def rewrite(self, source, target, mutate):
        with zipfile.ZipFile(source) as archive:
            content = {info.filename: archive.read(info) for info in archive.infolist()}
        mutate(content)
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in content.items():
                archive.writestr(name, data)

    def test_full_backup_roundtrip_keeps_unassigned_documents_reviews_and_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, campaign, document_id = self.fixture(root)
            archive = root / "backup.zip"
            result = backup.export_workspace(workspace, source, archive)
            self.assertTrue(result["verified"])
            self.assertTrue(result["evidence_complete"])
            self.assertFalse(result["authenticity_verified"])
            self.assertTrue(result["source_evidence_complete"])
            self.assertIn(document_id, result["documents"])
            restored = backup.restore_workspace_backup(archive, root / "restored")
            recovered = Path(restored["workspace"])
            self.assertEqual(load_results(campaign), load_results(recovered / campaign.relative_to(workspace)))
            self.assertEqual(load_document(workspace / "documents", document_id), load_document(recovered / "documents", document_id))
            self.assertTrue((recovered / campaign.relative_to(workspace) / "reviews/review-fixture/ratings_a.csv").is_file())
            commit = result["source_snapshots"]["current_commit"]
            self.assertEqual((root / "restored/snapshot/source" / commit / "main.py").read_bytes(), (source / "main.py").read_bytes())
            self.assertFalse((recovered / "exports").exists())
            self.assertFalse((recovered / "workers/retired.lock").exists())
            self.assertEqual(Path(restored["original_archive"]).read_bytes(), archive.read_bytes())
            self.assertEqual(backup.verify_workspace_backup(archive)["archive_sha256"], result["archive_sha256"])
            with self.assertRaises(FileExistsError):
                backup.restore_workspace_backup(archive, root / "restored")
            with self.assertRaises(FileExistsError):
                backup.export_workspace(workspace, source, archive)

    def test_rejects_changed_bytes_extra_members_schema_and_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, _, _ = self.fixture(root)
            archive = root / "backup.zip"
            backup.export_workspace(workspace, source, archive)
            def corrupt_schema(content):
                index = json.loads(content[backup.INDEX_NAME])
                index["schema_version"] = 2
                content[backup.INDEX_NAME] = json.dumps(index).encode()
            mutations = [lambda c: c.__setitem__("../escaped.txt", b"escape"),
                         lambda c: c.__setitem__("workspace/unindexed.txt", b"extra"),
                         lambda c: c.__setitem__(next(n for n in c if n.endswith("original.pdf")), b"tampered"),
                         corrupt_schema]
            for number, mutate in enumerate(mutations):
                with self.subTest(number=number):
                    bad = root / f"bad-{number}.zip"
                    self.rewrite(archive, bad, mutate)
                    with self.assertRaises(ValueError):
                        backup.restore_workspace_backup(bad, root / f"restore-{number}")
                    self.assertFalse((root / f"restore-{number}").exists())
            self.assertFalse((root / "escaped.txt").exists())

    def test_rejects_dirty_source_active_worker_unknown_files_and_internal_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, _, _ = self.fixture(root)
            with self.assertRaises(ValueError):
                backup.export_workspace(workspace, source, workspace / "backup.zip")
            (source / "main.py").write_text("changed")
            with self.assertRaisesRegex(ValueError, "tracked source"):
                backup.export_workspace(workspace, source, root / "dirty.zip")
            subprocess.run(["git", "checkout", "--", "main.py"], cwd=source, check=True)
            (workspace / ".env").write_text("synthetic unexpected entry")
            with self.assertRaisesRegex(ValueError, "Unknown workspace"):
                backup.export_workspace(workspace, source, root / "unknown.zip")
            (workspace / ".env").unlink()
            lease = _worker_lease(workspace / "workers/live.lock")
            try:
                with self.assertRaisesRegex(ValueError, "active worker"):
                    backup.export_workspace(workspace, source, root / "active.zip")
            finally:
                lease.close()
            self.assertFalse((root / "dirty.zip").exists())
            self.assertFalse((root / "active.zip").exists())

    def test_rejects_data_changes_during_export_without_publishing_partial_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, _, document_id = self.fixture(root)
            real_write = backup._write_snapshot
            def mutate_after_read(*args):
                value = real_write(*args)
                (workspace / "documents" / document_id / "extracted.txt").write_text("changed during snapshot")
                return value
            with patch.object(backup, "_write_snapshot", side_effect=mutate_after_read):
                with self.assertRaisesRegex(ValueError, "Workspace changed"):
                    backup.export_workspace(workspace, source, root / "changed.zip")
            self.assertFalse((root / "changed.zip").exists())
            self.assertFalse(list(root.glob(".workspace-*.zip")))

    def test_rejects_damaged_document_and_active_campaign(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, campaign, document_id = self.fixture(root)
            manifest = campaign / "manifest.json"
            value = json.loads(manifest.read_text())
            value["state"] = "running"
            manifest.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "active or unclosed"):
                backup.export_workspace(workspace, source, root / "running.zip")
            value["state"] = "completed"
            manifest.write_text(json.dumps(value))
            (workspace / "documents" / document_id / "original.pdf").write_bytes(b"damaged")
            with self.assertRaises(ValueError):
                backup.export_workspace(workspace, source, root / "damaged.zip")

    def test_size_limit_and_atomic_publication_failure_leave_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, _, _ = self.fixture(root)
            with patch.object(backup.archives, "MAX_TOTAL_BYTES", 1):
                with self.assertRaises(ValueError):
                    backup.export_workspace(workspace, source, root / "large.zip")
            with patch.object(backup.os, "link", side_effect=OSError("synthetic publication failure")):
                with self.assertRaises(OSError):
                    backup.export_workspace(workspace, source, root / "publish.zip")
            self.assertFalse((root / "publish.zip").exists())
            self.assertFalse(list(root.glob(".workspace-*.zip")))

    def test_cli_verify_restore_and_failure_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, _, _ = self.fixture(root)
            archive = root / "backup.zip"
            with patch("sys.stdout"), patch("sys.stderr"):
                self.assertEqual(backup.main(["export", "--workspace", str(workspace), "--source", str(source), "--output", str(archive), "--writers-stopped"]), 0)
                self.assertEqual(backup.main(["verify", str(archive)]), 0)
                self.assertEqual(backup.main(["restore", str(archive), str(root / "recovered")]), 0)
                self.assertEqual(backup.main(["verify", str(root / "missing.zip")]), 1)

    def test_historical_source_is_included_and_missing_revision_remains_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, campaign, _ = self.fixture(root)
            original = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
            (source / "main.py").write_text("# next revision\n")
            subprocess.run(["git", "-c", "user.name=Backup Test", "-c", "user.email=fixture@example.invalid", "commit", "-qam", "next"], cwd=source, check=True, capture_output=True)
            result = backup.export_workspace(workspace, source, root / "history.zip")
            self.assertTrue(result["source_evidence_complete"])
            self.assertEqual(len(result["source_snapshots"]["included_commits"]), 2)
            self.assertIn(original, result["source_snapshots"]["included_commits"])
            manifest = campaign / "manifest.json"
            value = json.loads(manifest.read_text())
            value["provenance"]["git_commit"] = "f" * 40
            manifest.write_text(json.dumps(value))
            incomplete = backup.export_workspace(workspace, source, root / "missing-code.zip")
            self.assertTrue(incomplete["verified"])
            self.assertFalse(incomplete["source_evidence_complete"])
            self.assertEqual(incomplete["source_snapshots"]["missing_commits"], ["f" * 40])

    def test_preserves_incomplete_campaign_without_claiming_complete_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, _, _ = self.fixture(root)
            cancelled = workspace / "campaigns/cancelled-fixture"
            run_batch(self.cases, cancelled, ScriptedModel, variants=["B"], sources=["clean"], should_cancel=lambda: True)
            result = backup.export_workspace(workspace, source, root / "partial.zip")
            self.assertTrue(result["verified"])
            self.assertTrue(result["evidence_complete"])
            self.assertFalse(result["campaigns_complete"])
            self.assertEqual(result["campaigns"]["campaigns/cancelled-fixture"]["campaign_state"], "cancelled")

    def test_legacy_review_sets_are_bound_to_preserved_campaigns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, campaign, _ = self.fixture(root)
            legacy = workspace / "reviews/legacy-review"
            export_review(load_results(campaign), legacy)
            result = backup.export_workspace(workspace, source, root / "legacy.zip")
            self.assertEqual(result["verified_root_reviews"], ["legacy-review"])
            mapping = legacy / "mapping.json"
            value = json.loads(mapping.read_text())
            next(iter(value["private_review_mapping"].values()))["result_sha256"] = "f" * 64
            mapping.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                backup.export_workspace(workspace, source, root / "orphaned-review.zip")

    def test_rehashed_document_tampering_fails_semantic_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, _, _ = self.fixture(root)
            archive = root / "backup.zip"
            backup.export_workspace(workspace, source, archive)
            def tamper(content):
                name = next(n for n in content if n.endswith("original.pdf"))
                content[name] = b"changed original"
                index = json.loads(content[backup.INDEX_NAME])
                index["files"][name] = {"size": len(content[name]), "sha256": hashlib.sha256(content[name]).hexdigest()}
                content[backup.INDEX_NAME] = json.dumps(index).encode()
            self.rewrite(archive, root / "tampered.zip", tamper)
            with self.assertRaises(ValueError):
                backup.verify_workspace_backup(root / "tampered.zip")

    def test_missing_manifests_and_dangling_worker_ownership_never_disappear(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, campaign, _ = self.fixture(root)
            manifest = campaign / "manifest.json"
            original = manifest.read_bytes()
            manifest.unlink()
            with self.assertRaisesRegex(ValueError, "missing manifest"):
                backup.export_workspace(workspace, source, root / "missing-manifest.zip")
            manifest.write_bytes(original)
            (workspace / "workers/missing.json").write_text(json.dumps({
                "schema_version": 1, "kind": "workbench_mock_worker", "campaign_id": "missing"}))
            with self.assertRaisesRegex(ValueError, "missing campaign evidence"):
                backup.export_workspace(workspace, source, root / "missing-campaign.zip")

    def test_racing_destination_creation_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, _, _ = self.fixture(root)
            archive, destination = root / "backup.zip", root / "restore"
            backup.export_workspace(workspace, source, archive)
            real_verify = backup._verify_into
            def rival_creates_directory(*args):
                result = real_verify(*args)
                destination.mkdir()
                return result
            with patch.object(backup, "_verify_into", side_effect=rival_creates_directory):
                with self.assertRaises(FileExistsError):
                    backup.restore_workspace_backup(archive, destination)
            self.assertTrue(destination.is_dir())
            self.assertEqual(list(destination.iterdir()), [])

    def test_empty_legacy_reviews_do_not_reload_all_campaign_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "reviews").mkdir()
            with patch.object(backup, "load_results", side_effect=AssertionError("unnecessary full load")):
                self.assertEqual(backup._check_root_reviews(root), [])
