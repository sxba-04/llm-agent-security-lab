"""Display labels, filtered CSVs and concurrent drafts preserve original evidence."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
import csv
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path
import tempfile
import threading
from unittest.mock import patch
import time
import unittest

from fastapi.testclient import TestClient

from security_lab import batch
from security_lab.archives import export_campaign, import_campaign
from security_lab.campaign_metadata import load_metadata, save_metadata
from security_lab.comparison_csv import comparison_csv
from security_lab.server import create_app

CASES = Path(__file__).resolve().parents[1] / 'cases' / 'dev'


class CampaignComfortTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.workspace = self.root / 'workspace'
        self.app = create_app(self.workspace, CASES)
        self.client = self.enterContext(TestClient(self.app, base_url='http://127.0.0.1'))
        self.headers = {'X-Lab-Token': self.client.get('/api/health').json()['csrf_token']}
        case = self.client.get('/api/cases').json()['cases'][0]['case_id']
        response = self.client.post('/api/campaigns', headers=self.headers, json={
            'case_ids': [case], 'variants': ['B', 'P'], 'sources': ['clean', 'attack'],
            'display_name': 'PDF-Abnahme', 'tags': ['Abnahme', 'Mock'],
        })
        self.assertEqual(response.status_code, 202, response.text)
        self.campaign = response.json()['campaign_id']
        deadline = time.monotonic() + 10
        while self.app.state.jobs.running:
            self.assertLess(time.monotonic(), deadline)
            time.sleep(.01)
        self.path = self.workspace / 'campaigns' / self.campaign
        self.url = '/api/campaigns/' + self.campaign

    def _review(self):
        identifier = self.client.post(self.url + '/review-export', headers=self.headers).json()['review_set_id']
        url = f'/api/reviews/{identifier}/ratings/a'
        packet = self.client.get(f'/api/reviews/{identifier}/packets').json()['packets'][0]
        return url, {'rater': 'Synthetic A', 'ratings': [{
            'review_id': packet['review_id'], 'notes': 'Synthetic draft for concurrency verification.',
        }]}

    def test_metadata_history_round_trips_without_changing_original_records(self):
        originals = {path: path.read_bytes() for path in self.path.glob('records/*.json')}
        self.assertEqual(self.client.get(self.url + '/metadata').json()['revision'], 1)
        updated = self.client.put(self.url + '/metadata', headers=self.headers, json={
            'display_name': 'Kontrolllauf nach Abnahme', 'tags': ['Kontrolle'], 'expected_revision': 1,
        })
        self.assertEqual(updated.status_code, 200, updated.text)
        brief = self.client.get('/api/campaigns').json()['campaigns'][0]
        self.assertEqual(brief['display_name'], 'Kontrolllauf nach Abnahme')
        self.assertEqual(brief['tags'], ['Kontrolle'])
        self.assertEqual(brief['metadata_revision'], 2)
        self.assertEqual({path: path.read_bytes() for path in originals}, originals)
        archive = self.root / 'campaign.zip'
        export_campaign(self.path, archive)
        imported = self.root / 'restored'
        import_campaign(archive, imported)
        self.assertEqual(load_metadata(imported), updated.json())
        self.assertEqual(len(list((imported / 'campaign-metadata').glob('*.json'))), 2)

    def test_listing_waits_for_atomic_metadata_publication(self):
        entered, release = threading.Event(), threading.Event()
        original_link = batch.os.link
        def blocked_link(source, destination, **kwargs):
            if Path(destination).name == 'metadata-000002.json':
                entered.set()
                if not release.wait(5):
                    raise RuntimeError('Test publication gate timed out')
            return original_link(source, destination, **kwargs)
        with patch('security_lab.batch.os.link', side_effect=blocked_link), ThreadPoolExecutor(max_workers=2) as pool:
            writer = pool.submit(save_metadata, self.path, 'Concurrent label', [], 1)
            try:
                self.assertTrue(entered.wait(5))
                reader = pool.submit(self.app.state.jobs.list)
                with self.assertRaises(TimeoutError):
                    reader.result(timeout=.05)
            finally:
                release.set()
            writer.result(timeout=5)
            brief = reader.result(timeout=5)[0]
        self.assertTrue(brief['valid_evidence'])
        self.assertEqual(brief['state'], 'completed')
        self.assertEqual(brief['display_name'], 'Concurrent label')

    def test_stale_metadata_and_invalid_labels_cannot_change_saved_name(self):
        url = self.url + '/metadata'
        before = self.client.get(url).json()
        for name, tags, revision, status in [('stale', [], 0, 409), ('bad\nname', [], 1, 400),
                                           ('valid', ['Tag', 'tag'], 1, 400), ('valid', ['x' * 41], 1, 400)]:
            result = self.client.put(url, headers=self.headers, json={
                'display_name': name, 'tags': tags, 'expected_revision': revision,
            })
            self.assertEqual(result.status_code, status, result.text)
            self.assertEqual(self.client.get(url).json(), before)

    def test_metadata_chain_damage_and_future_schema_rejected(self):
        save_metadata(self.path, 'Second name', [], 1)
        first = self.path / 'campaign-metadata' / 'metadata-000001.json'
        original = first.read_bytes()
        value = json.loads(original)
        value['display_name'] = 'Changed original'
        first.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'Metadatenhistorie'):
            load_metadata(self.path)
        first.write_bytes(original)
        second = first.with_name('metadata-000002.json')
        value = json.loads(second.read_bytes())
        value['schema_version'] = 2
        second.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'Nicht unterstützte'):
            export_campaign(self.path, self.root / 'damaged.zip')

    def test_legacy_campaign_metadata_is_additive_and_missing_history_detected(self):
        legacy = self.root / 'legacy'
        legacy.mkdir()
        self.assertEqual(load_metadata(legacy)['revision'], 0)
        save_metadata(legacy, '', [], 0)
        save_metadata(legacy, 'Later label', [], 1)
        (legacy / 'campaign-metadata' / 'metadata-000001.json').unlink()
        with self.assertRaisesRegex(ValueError, 'Metadatenhistorie'):
            load_metadata(legacy)

    def test_unrenderable_imported_labels_are_rejected_and_isolated(self):
        with self.assertRaisesRegex(ValueError, 'Unicode'):
            save_metadata(self.path, 'bad\ud800', [], 1)
        shutil.copytree(self.path, self.workspace / 'healthy-copy')
        first = self.path / 'campaign-metadata' / 'metadata-000001.json'
        value = json.loads(first.read_bytes())
        value['tags'] = ['bad\udfff']
        first.write_text(json.dumps(value))
        response = self.client.get('/api/campaigns')
        self.assertEqual(response.status_code, 200, response.text)
        rows = response.json()['campaigns']
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(row['valid_evidence'] for row in rows), 1)
        damaged = next(row for row in rows if row['campaign_id'] == self.campaign)
        self.assertEqual(damaged['state'], 'damaged')
        with self.assertRaisesRegex(ValueError, 'Unicode'):
            export_campaign(self.path, self.root / 'bad-unicode.zip')

    def test_metadata_rejects_duplicate_keys_and_large_untrusted_file(self):
        first = self.path / 'campaign-metadata' / 'metadata-000001.json'
        original = first.read_text()
        first.write_text(original.replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1'))
        with self.assertRaisesRegex(ValueError, 'Doppelte'):
            load_metadata(self.path)
        first.write_bytes(b' ' * 8193)
        with self.assertRaisesRegex(ValueError, 'Größenbegrenzung'):
            load_metadata(self.path)

    def test_process_death_residue_preserves_listing_archive_and_further_appends(self):
        script = """
import os, sys
from pathlib import Path
from security_lab import batch
from security_lab.campaign_metadata import save_metadata
original = batch.os.link
def interrupted(source, destination):
    if sys.argv[2] == 'after':
        original(source, destination)
    os._exit(23)
batch.os.link = interrupted
save_metadata(Path(sys.argv[1]), 'Interrupted save', [], 1)
"""
        for phase in ('before', 'after'):
            with self.subTest(phase=phase):
                campaign = self.workspace / ('crash-' + phase)
                shutil.copytree(self.path, campaign)
                result = subprocess.run([sys.executable, '-c', script, str(campaign), phase],
                                        capture_output=True, check=False, timeout=10)
                self.assertEqual(result.returncode, 23, result.stderr.decode(errors='replace'))
                residue = next((campaign / 'campaign-metadata').glob('*.tmp'))
                original_bytes = residue.read_bytes()
                metadata = load_metadata(campaign)
                expected_revision = 1 if phase == 'before' else 2
                self.assertEqual(metadata['revision'], expected_revision)
                self.assertEqual(metadata['unpublished_writes'], [residue.name])
                rows = self.app.state.jobs.list()
                brief = next(row for row in rows if row['campaign_id'] != self.campaign
                             and row['display_name'] == metadata['display_name']
                             and row['metadata_unpublished_writes'] == 1)
                self.assertTrue(brief['valid_evidence'])
                self.assertEqual(brief['state'], 'completed')
                output = self.root / (phase + '.zip')
                report = export_campaign(campaign, output)
                relative = 'campaign-metadata/' + residue.name
                self.assertEqual(report['unpublished_metadata_writes'], [relative])
                restored = self.root / ('restored-' + phase)
                import_campaign(output, restored)
                self.assertEqual((restored / relative).read_bytes(), original_bytes)
                updated = save_metadata(restored, 'Continued after inspection', [], expected_revision)
                self.assertEqual(updated['revision'], expected_revision + 1)
                self.assertEqual((restored / relative).read_bytes(), original_bytes)
                self.assertEqual(load_metadata(restored)['display_name'], 'Continued after inspection')

    def test_only_bounded_known_publisher_residue_is_tolerated(self):
        directory = self.path / 'campaign-metadata'
        residue = directory / 'metadata-000002.json.0123456789abcdef.tmp'
        residue.write_bytes(b'{"display_name": "partial')
        self.assertEqual(load_metadata(self.path)['revision'], 1)
        self.assertEqual(load_metadata(self.path)['unpublished_writes'], [residue.name])
        self.assertEqual(residue.read_bytes(), b'{"display_name": "partial')
        cases = [('arbitrary.tmp', b'preserve unknown'),
                 ('metadata-000002.json.not-a-publisher.tmp', b'unknown publisher'),
                 ('metadata-000999.json.0123456789abcdef.tmp', b'impossible revision'),
                 ('metadata-000002.json.abcdef0123456789.tmp', b'x' * 8193)]
        for name, content in cases:
            with self.subTest(name=name):
                path = directory / name
                path.write_bytes(content)
                try:
                    with self.assertRaises(ValueError):
                        load_metadata(self.path)
                    with self.assertRaises(ValueError):
                        export_campaign(self.path, self.root / 'invalid.zip')
                    self.assertEqual(path.read_bytes(), content)
                finally:
                    path.unlink()
        outside = self.path / 'records' / residue.name
        outside.write_bytes(b'not a metadata publisher location')
        try:
            with self.assertRaisesRegex(ValueError, 'unfinished temporary write'):
                export_campaign(self.path, self.root / 'outside.zip')
        finally:
            outside.unlink()
        committed = directory / 'metadata-000001.json'
        committed.write_text('{"corrupt":')
        with self.assertRaises(ValueError):
            load_metadata(self.path)
        self.assertEqual(residue.read_bytes(), b'{"display_name": "partial')

    def test_metadata_filenames_reject_non_ascii_digits(self):
        directory = self.path / 'campaign-metadata'
        canonical = directory / 'metadata-000001.json'
        original = canonical.read_bytes()
        for digits in ('٠٠٠٠٠١', '０００００１', '00000١'):
            for suffix in ('.json', '.json.0123456789abcdef.tmp'):
                with self.subTest(digits=digits, suffix=suffix):
                    unexpected = directory / ('metadata-' + digits + suffix)
                    unexpected.write_bytes(original)
                    try:
                        with self.assertRaisesRegex(ValueError, 'Unbekannte'):
                            load_metadata(self.path)
                    finally:
                        unexpected.unlink()
        self.assertEqual(load_metadata(self.path)['revision'], 1)

    def test_parallel_rating_changes_reject_stale_writer_and_keep_original(self):
        url, body = self._review()
        revision = self.client.get(url).json()['revision']
        first = {**body, 'expected_revision': revision}
        second = {**first, 'rater': 'Synthetic other tab'}
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda value: self.client.put(url, headers=self.headers, json=value), [first, second]))
        self.assertEqual(sorted(result.status_code for result in outcomes), [200, 409])
        saved = self.client.get(url).json()
        self.assertEqual(saved['revision'], 1)
        preserved = {path: path.read_bytes() for path in self.path.glob('reviews/*/drafts-a/*.json')}
        stale = self.client.put(url, headers=self.headers, json=first)
        self.assertEqual(stale.status_code, 409)
        self.assertEqual({path: path.read_bytes() for path in preserved}, preserved)
        updated = self.client.put(url, headers=self.headers, json={**body, 'expected_revision': 1, 'rater': 'Synthetic revision'})
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()['revision'], 2)
        self.assertEqual({path: path.read_bytes() for path in preserved}, preserved)

    def test_older_client_can_create_but_cannot_overwrite_unobserved_revision(self):
        url, body = self._review()
        self.assertEqual(self.client.put(url, headers=self.headers, json=body).status_code, 200)
        result = self.client.put(url, headers=self.headers, json={**body, 'rater': 'Unversioned change'})
        self.assertEqual(result.status_code, 409, result.text)
        self.assertIn('Oberfläche aktualisieren', result.json()['detail'])
        self.assertEqual(self.client.get(url).json()['rater'], 'Synthetic A')

    def test_workspace_backup_endpoint_rejects_active_operations_and_cleans_download(self):
        api = next(route.endpoint.__self__ for route in self.app.routes if route.path == '/api/workspace/backup')
        with patch('security_lab.backup.export_workspace') as export:
            api.extraction_slot.acquire()
            try:
                response = self.client.get('/api/workspace/backup')
            finally:
                api.extraction_slot.release()
            self.assertEqual(response.status_code, 409)
            api.jobs._active = self.campaign
            try:
                response = self.client.get('/api/workspace/backup')
            finally:
                api.jobs._active = None
            self.assertEqual(response.status_code, 409)
            export.assert_not_called()
        outputs = []
        def fake_export(workspace, source_root, destination):
            self.assertEqual(workspace, self.workspace)
            self.assertFalse(destination.is_relative_to(self.workspace))
            destination.write_bytes(b'synthetic verified snapshot')
            outputs.append(destination)
        with patch('security_lab.backup.export_workspace', side_effect=fake_export):
            response = self.client.get('/api/workspace/backup')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'synthetic verified snapshot')
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertFalse(outputs[0].parent.exists())

    def test_backup_temporary_storage_failure_releases_extraction_slot(self):
        api = next(route.endpoint.__self__ for route in self.app.routes if route.path == '/api/workspace/backup')
        with patch('security_lab.server.tempfile.TemporaryDirectory', side_effect=OSError('Synthetic disk full')):
            with self.assertRaises(OSError):
                self.client.get('/api/workspace/backup')
        self.assertTrue(api.extraction_slot.acquire(blocking=False))
        api.extraction_slot.release()

    def test_csv_exports_same_filters_counts_and_pending_not_zero(self):
        metric = 'legitimate_success'
        response = self.client.get(self.url + '/comparison.csv', params={'metric': metric, 'source': 'attack'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.headers['content-type'].startswith('text/csv'))
        self.assertIn('attachment;', response.headers['content-disposition'])
        rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual({row['source'] for row in rows}, {'attack'})
        self.assertEqual({row['metric'] for row in rows}, {metric})
        self.assertEqual({row['row_type'] for row in rows}, {'group', 'pair', 'case'})
        pending = [row for row in rows if int(row['pending']) > 0]
        self.assertTrue(pending)
        self.assertTrue(all(row['denominator'] == '0' for row in pending))
        self.assertTrue(all(row['rate'] == '' for row in pending))
        report = self.client.get(self.url + '/summary').json()
        exported = [row for row in rows if row['row_type'] == 'group']
        expected = [group for group in report['groups'] if group['source'] == 'attack']
        self.assertEqual(sum(int(row['pending']) for row in exported), sum(group['metrics'][metric]['pending'] for group in expected))
        self.assertEqual(self.client.get(self.url + '/comparison.csv', params={'metric': 'invented'}).status_code, 400)

    def test_spreadsheet_formula_labels_are_escaped_but_negative_differences_numeric(self):
        summary = {'groups': [{'variant': '=SUM(1,2)', 'source': 'clean', 'goal': 'G1', 'model': '\t=CMD()',
                               'metrics': {'backend_violation': {'numerator': 0, 'denominator': 1, 'rate': 0}}}],
                   'paired_comparisons': {'comparisons': [{'source': 'clean', 'goal': 'G1', 'metrics': {
                       'backend_violation': {'difference_pp': -100, 'denominator': 1}}}]}}
        content = comparison_csv(summary, 'stable-id', display_name='  +malicious')
        rows = list(csv.DictReader(io.StringIO(content)))
        self.assertEqual(rows[0]['variant'], "'=SUM(1,2)")
        self.assertEqual(rows[0]['model'], "'\t=CMD()")
        self.assertEqual(rows[0]['display_name'], "'  +malicious")
        self.assertEqual(rows[1]['difference_pp'], '-100')


if __name__ == '__main__':
    unittest.main()
