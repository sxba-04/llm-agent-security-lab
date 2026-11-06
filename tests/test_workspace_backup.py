import hashlib
import json
import shutil
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

    def test_metadata_publisher_residue_is_preserved_and_reported_through_backup_restore(self):
        from security_lab.campaign_metadata import load_metadata, save_metadata
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, campaign, _ = self.fixture(root)
            save_metadata(campaign, "Published name", [], 0)
            relative = Path("campaign-metadata/metadata-000002.json.0123456789abcdef.tmp")
            content = b'{"display_name": "interrupted bytes'
            (campaign / relative).write_bytes(content)
            result = backup.export_workspace(workspace, source, root / "backup.zip")
            campaign_key = campaign.relative_to(workspace).as_posix()
            self.assertEqual(result["campaigns"][campaign_key]["unpublished_metadata_writes"], [relative.as_posix()])
            self.assertTrue(result["verified"])
            restored = backup.restore_workspace_backup(root / "backup.zip", root / "restored")
            recovered = Path(restored["workspace"]) / campaign_key
            self.assertEqual((recovered / relative).read_bytes(), content)
            self.assertEqual(load_metadata(recovered)["display_name"], "Published name")
            save_metadata(recovered, "New published name", [], 1)
            self.assertEqual(load_metadata(recovered)["revision"], 2)
            self.assertEqual((recovered / relative).read_bytes(), content)
            self.assertEqual((campaign / relative).read_bytes(), content)

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

    def test_documented_operational_evidence_roundtrip_is_reported_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, _, document_id = self.fixture(root)
            proof = workspace / "operations/persistence-20261102"
            technical_campaign = proof / "campaign"
            run_batch(self.cases, technical_campaign, ScriptedModel, variants=["B", "F", "P"], sources=["clean"])
            shutil.copytree(workspace / "documents" / document_id, proof / "documents" / document_id)
            backup.archives.export_campaign(technical_campaign, proof / "campaign.zip")
            checksums = {path.relative_to(proof).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in proof.rglob("*") if path.is_file()}
            (proof / "checksums.json").write_text(json.dumps(checksums))
            originals = {path.relative_to(workspace): path.read_bytes()
                         for path in proof.rglob("*") if path.is_file()}
            archive = root / "operational.zip"
            result = backup.export_workspace(workspace, source, archive)
            self.assertEqual(list(result["campaigns"]), ["campaigns/campaign-fixture"])
            self.assertEqual(result["documents"], [document_id])
            self.assertTrue(result["source_evidence_complete"])
            self.assertEqual(len(result["supplementary_operations"]), 1)
            operational = result["supplementary_operations"][0]
            self.assertEqual(operational["path"], "operations/persistence-20261102")
            self.assertEqual(operational["file_count"], len(originals))
            self.assertEqual(operational["verification"], "backup_inventory_and_sha256_only")
            self.assertFalse(operational["semantic_evidence_verified"])
            self.assertFalse(operational["included_in_scientific_campaign_totals"])
            restored = backup.restore_workspace_backup(archive, root / "restored")
            for path, content in originals.items():
                self.assertEqual((Path(restored["workspace"]) / path).read_bytes(), content)
            self.assertEqual(backup.verify_workspace_backup(archive)["supplementary_operations"], result["supplementary_operations"])
            self.assertFalse((Path(restored["workspace"]) / "operations/persistence-20261102/documents" / document_id / "confirmation.json").exists())

    def test_operational_evidence_remains_byte_checked_without_semantic_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, _, _ = self.fixture(root)
            proof = workspace / "operations/persistence-20261102"
            proof.mkdir(parents=True)
            (proof / "checksums.json").write_text("historical opaque diagnostic record")
            archive = root / "opaque-proof.zip"
            result = backup.export_workspace(workspace, source, archive)
            self.assertFalse(result["supplementary_operations"][0]["semantic_evidence_verified"])
            name = "workspace/operations/persistence-20261102/checksums.json"
            self.rewrite(archive, root / "changed-proof.zip", lambda content: content.__setitem__(name, b"changed"))
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                backup.verify_workspace_backup(root / "changed-proof.zip")

    def test_other_operational_roots_and_symlinks_are_not_implicitly_authorized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, _, _ = self.fixture(root)
            unknown = workspace / "operations/secrets"
            unknown.mkdir(parents=True)
            (unknown / "credentials.json").write_text("synthetic unexpected entry")
            with self.assertRaisesRegex(ValueError, "Unknown operational"):
                backup.export_workspace(workspace, source, root / "unknown-operations.zip")
            shutil.rmtree(unknown)
            proof = workspace / "operations/persistence-20261102"
            proof.mkdir()
            outside = root / "outside.txt"
            outside.write_text("must not be read into the archive")
            link = proof / "linked.txt"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("File symlinks unavailable on this platform")
            with self.assertRaises(ValueError):
                backup.export_workspace(workspace, source, root / "linked-operations.zip")

    def test_legacy_campaign_named_like_canonical_root_still_gets_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, campaign, _ = self.fixture(root)
            legacy = workspace / "studies"
            shutil.copytree(campaign, legacy)
            result = backup.export_workspace(workspace, source, root / "legacy-name.zip")
            self.assertIn("studies", result["campaigns"])
            next((legacy / "records").glob("*.json")).write_text("damaged original")
            with self.assertRaises(ValueError):
                backup.export_workspace(workspace, source, root / "damaged-legacy-name.zip")

    def test_exports_campaign_roundtrip_preserves_originals_while_plain_cache_is_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, campaign, _ = self.fixture(root)
            cache_only = root / "cache-only.zip"
            initial = backup.export_workspace(workspace, source, cache_only)
            self.assertEqual(len(initial["campaigns"]), 1)
            with zipfile.ZipFile(cache_only) as archive:
                self.assertFalse(any(name.startswith("workspace/exports/") for name in archive.namelist()))
            legacy = workspace / "exports"
            shutil.copytree(campaign, legacy, dirs_exist_ok=True)
            originals = {path.relative_to(workspace): hashlib.sha256(path.read_bytes()).hexdigest()
                         for directory in (campaign, legacy)
                         for path in directory.rglob("*") if path.is_file()}
            before = backup._check_workspace(workspace)
            self.assertEqual(set(before["campaigns"]), {"campaigns/campaign-fixture", "exports"})
            result = backup.export_workspace(workspace, source, root / "two-campaigns.zip")
            self.assertEqual(set(result["campaigns"]), set(before["campaigns"]))
            restored = backup.restore_workspace_backup(root / "two-campaigns.zip", root / "restored")
            recovered = Path(restored["workspace"])
            self.assertEqual(set(restored["campaigns"]), set(before["campaigns"]))
            for relative, expected in originals.items():
                self.assertEqual(hashlib.sha256((recovered / relative).read_bytes()).hexdigest(), expected)
            self.assertEqual(load_results(recovered / "exports"), load_results(legacy))

    def test_ambiguous_export_cache_and_nonfile_manifests_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, _, _ = self.fixture(root)
            records = workspace / "exports/records"
            records.mkdir()
            (records / "original.json").write_text("preserve possible crash evidence")
            with self.assertRaisesRegex(ValueError, "Ambiguous exports"):
                backup.export_workspace(workspace, source, root / "ambiguous.zip")
            self.assertEqual((records / "original.json").read_text(), "preserve possible crash evidence")
            for name in ("exports", "studies", "metadata"):
                with self.subTest(directory=name):
                    manifest = workspace / name / "manifest.json"
                    manifest.mkdir(parents=True)
                    with self.assertRaisesRegex(ValueError, "manifest is not a regular file"):
                        backup.export_workspace(workspace, source, root / (name + "-bad.zip"))
                    self.assertTrue(manifest.is_dir())
                    manifest.rmdir()

    def test_inventory_omission_never_publishes_verified_backup_with_fewer_campaigns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, campaign, _ = self.fixture(root)
            shutil.copytree(campaign, workspace / "exports", dirs_exist_ok=True)
            real_inventory = backup._workspace_files
            def omit_legacy(directory):
                return [item for item in real_inventory(directory) if not item[0].startswith("workspace/exports/")]
            with patch.object(backup, "_workspace_files", side_effect=omit_legacy):
                with self.assertRaisesRegex(ValueError, "campaign inventory differs"):
                    backup.export_workspace(workspace, source, root / "omitted.zip")
            self.assertFalse((root / "omitted.zip").exists())

    def test_nested_lock_named_evidence_is_preserved_while_direct_worker_locks_are_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, source, _, _ = self.fixture(root)
            nested = workspace / "workers/audit/proof.lock"
            nested.parent.mkdir()
            content = b"original audit evidence; not a direct worker lease"
            nested.write_bytes(content)
            backup.export_workspace(workspace, source, root / "locks.zip")
            with zipfile.ZipFile(root / "locks.zip") as archive:
                self.assertEqual(archive.read("workspace/workers/audit/proof.lock"), content)
                self.assertNotIn("workspace/workers/retired.lock", archive.namelist())
            restored = backup.restore_workspace_backup(root / "locks.zip", root / "restored")
            recovered = Path(restored["workspace"]) / nested.relative_to(workspace)
            self.assertEqual(hashlib.sha256(recovered.read_bytes()).hexdigest(), hashlib.sha256(content).hexdigest())
