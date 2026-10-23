import hashlib
import copy
import csv
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from security_lab.archives import export_campaign, verify_archive, import_campaign
from security_lab.batch import run_batch, load_results
from security_lab.cases import load_cases
from security_lab.models import ScriptedModel
from security_lab.evaluation import summarize
from security_lab.review import (RATING_FIELDS, adjudicate_review, attach_reviews,
                                 combine_reviews, export_review, validate_combined)


class ArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases=load_cases(Path(__file__).parents[1]/'cases/dev')[:1]

    def campaign(self,root):
        campaign=root/'campaign'
        run_batch(self.cases,campaign,ScriptedModel,variants=['B'],sources=['clean'])
        return campaign

    def pdf_campaign(self, root):
        case = copy.deepcopy(self.cases[0])
        original = b'%PDF-synthetic-archive-evidence'
        extracted = case['articles']['clean'].encode('utf-8')
        document_id = 'doc-' + 'a' * 32
        metadata = {'document_id': document_id, 'filename': 'article.pdf',
                    'sha256': hashlib.sha256(original).hexdigest(),
                    'text_sha256': hashlib.sha256(extracted).hexdigest(),
                    'page_count': 1, 'extractor': 'synthetic-test-fixture', 'origin': 'uploaded_pdf'}
        case['article_sources'] = {'clean': {**metadata, 'confirmed': True}}
        campaign = root / 'campaign'
        run_batch([case], campaign, ScriptedModel, variants=['B'], sources=['clean'])
        source = campaign / 'sources' / document_id
        source.mkdir(parents=True)
        (source / 'original.pdf').write_bytes(original)
        (source / 'extracted.txt').write_bytes(extracted)
        (source / 'document.json').write_text(json.dumps(metadata))
        (source / 'confirmation.json').write_text(json.dumps({'text_sha256': metadata['text_sha256']}))
        return campaign, source

    def rewrite(self,source,target,mutate):
        with zipfile.ZipFile(source) as archive:
            content={i.filename:archive.read(i) for i in archive.infolist()}
        mutate(content)
        with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,data in content.items():
                archive.writestr(name,data)

    def review_history(self, campaign):
        directory = campaign / 'reviews' / 'review-test'
        paths = {key: Path(value) for key, value in export_review(load_results(campaign), directory).items()}
        ids = list(json.loads(paths['mapping'].read_text())['private_review_mapping'])
        submission = directory / 'submissions' / 'submission-test'
        submission.mkdir(parents=True)
        ratings = []
        for slot, rater in (('a', 'Alice'), ('b', 'Bob')):
            path = submission / f'ratings_{slot}.csv'
            with path.open('w', encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=RATING_FIELDS)
                writer.writeheader()
                writer.writerows({'review_id': identifier, 'rater': rater, 'legitimate_rating': 'correct',
                                  'attack_success': 'yes' if slot == 'a' else 'no', 'false_block': 'no',
                                  'notes': 'Synthetic test rating; original evidence checked.'} for identifier in ids)
            ratings.append(path)
        first = directory / 'combined' / 'combined-000001.json'
        baseline = combine_reviews(paths['mapping'], ratings, first, packets_path=paths['reviews'])
        updated = adjudicate_review(baseline, ids[0], legitimate_rating='correct', attack_success='no', false_block='no',
                                    rationale='Both reviewers checked the original synthetic answer.', adjudicators=['Alice', 'Bob'])
        second = first.with_name('combined-000002.json')
        second.write_text(json.dumps(updated, ensure_ascii=False), encoding='utf-8')
        return paths, ratings, first, second

    @staticmethod
    def rehash_review(value):
        value.pop('content_sha256', None)
        value['content_sha256'] = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()

    @staticmethod
    def rehash_member(content, name):
        index = json.loads(content['archive-index.json'])
        index['files'][name] = {'size': len(content[name]), 'sha256': hashlib.sha256(content[name]).hexdigest()}
        content['archive-index.json'] = json.dumps(index).encode()

    def test_roundtrip_preserves_evidence_reviews_and_original_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); campaign, source=self.pdf_campaign(root)
            export_review(load_results(campaign),campaign/'reviews'/'first')
            archive=root/'campaign.zip'
            report=export_campaign(campaign,archive)
            self.assertTrue(report['verified'])
            self.assertFalse(report['source_code_included'])
            self.assertFalse(report['authenticity_verified'])
            imported=import_campaign(archive,root/'restored')
            self.assertEqual(load_results(campaign),load_results(root/'restored'))
            self.assertEqual((root/'restored'/source.relative_to(campaign)/'original.pdf').read_bytes(),(source/'original.pdf').read_bytes())
            self.assertEqual(report['verified_document_sources'], [source.name])
            self.assertTrue(report['evidence_complete'])
            self.assertEqual(Path(imported['original_archive']).read_bytes(),archive.read_bytes())
            self.assertEqual(verify_archive(archive)['completed_runs'],1)
            with self.assertRaises(FileExistsError):
                import_campaign(archive,root/'restored')
            with self.assertRaises(FileExistsError):
                export_campaign(campaign,archive)

    def test_hash_tamper_rejected_and_import_destination_not_created(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); archive=root/'valid.zip'
            export_campaign(self.campaign(root),archive)
            bad=root/'bad.zip'
            self.rewrite(archive,bad,lambda content:content.__setitem__('summary.json',b'{}'))
            with self.assertRaisesRegex(ValueError,'hash mismatch'):
                verify_archive(bad)
            with self.assertRaises(ValueError):
                import_campaign(bad,root/'rejected')
            self.assertFalse((root/'rejected').exists())

    def test_paths_links_duplicates_and_excessive_expansion_rejected(self):
        for name in ('../escape','/absolute','C:/escape','folder\\escape','CON.txt'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/'bad.zip'
                with zipfile.ZipFile(path,'w') as archive:
                    archive.writestr(name,b'x')
                with self.assertRaises(ValueError):
                    verify_archive(path)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'link.zip'
            info=zipfile.ZipInfo('link'); info.create_system=3
            info.external_attr=(stat.S_IFLNK|0o777)<<16
            with zipfile.ZipFile(path,'w') as archive:
                archive.writestr(info,b'../../outside')
            with self.assertRaisesRegex(ValueError,'link or special'):
                verify_archive(path)
            path=Path(temp)/'bomb.zip'
            with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('oversized',b'x'*2000)
            with patch('security_lab.archives.MAX_TOTAL_BYTES',1000),self.assertRaisesRegex(ValueError,'expanded size'):
                verify_archive(path)
            path=Path(temp)/'collision.zip'
            with zipfile.ZipFile(path,'w') as archive:
                archive.writestr('File.json',b'a'); archive.writestr('file.json',b'b')
            with self.assertRaisesRegex(ValueError,'Duplicate'):
                verify_archive(path)

    def test_archive_manifest_inconsistency_is_rejected_even_with_matching_index(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); valid=root/'valid.zip'; bad=root/'bad.zip'
            export_campaign(self.campaign(root),valid)
            def tamper(content):
                manifest=json.loads(content['manifest.json'])
                manifest['completed_runs']=99
                content['manifest.json']=json.dumps(manifest).encode()
                index=json.loads(content['archive-index.json'])
                index['files']['manifest.json']={'size':len(content['manifest.json']),'sha256':hashlib.sha256(content['manifest.json']).hexdigest()}
                content['archive-index.json']=json.dumps(index).encode()
            self.rewrite(valid,bad,tamper)
            with self.assertRaisesRegex(ValueError,'progress count'):
                verify_archive(bad)

    def test_cancelled_campaign_archives_but_running_campaign_does_not(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); campaign=root/'cancelled'
            run_batch(self.cases,campaign,ScriptedModel,variants=['B'],sources=['clean'],should_cancel=lambda:True)
            report=export_campaign(campaign,root/'cancelled.zip')
            self.assertEqual(report['campaign_state'],'cancelled')
            manifest=json.loads((campaign/'manifest.json').read_text()); manifest['state']='running'
            (campaign/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'active or unclosed'):
                export_campaign(campaign,root/'running.zip')

    def test_export_rejects_symlinks_and_inside_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); campaign=self.campaign(root)
            with self.assertRaisesRegex(ValueError,'outside'):
                export_campaign(campaign,campaign/'archive.zip')
            outside=root/'outside.txt'; outside.write_text('private')
            try:
                (campaign/'extra.txt').symlink_to(outside)
            except OSError:
                self.skipTest('Symlinks unavailable on this host')
            with self.assertRaisesRegex(ValueError,'symbolic link'):
                export_campaign(campaign,root/'rejected.zip')

    def test_pdf_original_extraction_metadata_confirmation_and_missing_files_rejected(self):
        for filename in ('original.pdf', 'extracted.txt', 'document.json', 'confirmation.json', 'missing'):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                campaign, source = self.pdf_campaign(root)
                if filename == 'missing':
                    (source / 'original.pdf').unlink()
                elif filename.endswith('.json'):
                    data = json.loads((source / filename).read_text())
                    data['text_sha256'] = '0' * 64
                    (source / filename).write_text(json.dumps(data))
                else:
                    (source / filename).write_bytes(b'changed evidence')
                with self.assertRaisesRegex(ValueError, 'PDF source'):
                    export_campaign(campaign, root / 'rejected.zip')
                self.assertFalse((root / 'rejected.zip').exists())

    def test_rehashed_zip_cannot_replace_original_pdf_or_remove_referenced_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            campaign, source = self.pdf_campaign(root)
            valid = root / 'valid.zip'
            export_campaign(campaign, valid)
            original_name = (source.relative_to(campaign) / 'original.pdf').as_posix()
            for remove in (False, True):
                bad = root / f'bad-{remove}.zip'
                def tamper(content):
                    index = json.loads(content['archive-index.json'])
                    if remove:
                        del content[original_name]
                        del index['files'][original_name]
                    else:
                        content[original_name] = b'%PDF-replacement'
                        index['files'][original_name] = {'size': len(content[original_name]), 'sha256': hashlib.sha256(content[original_name]).hexdigest()}
                    content['archive-index.json'] = json.dumps(index).encode()
                self.rewrite(valid, bad, tamper)
                with self.assertRaisesRegex(ValueError, 'PDF source'):
                    verify_archive(bad)
                with self.assertRaises(ValueError):
                    import_campaign(bad, root / f'rejected-{remove}')
                self.assertFalse((root / f'rejected-{remove}').exists())

    def test_foreign_review_set_rejected_despite_identical_local_run_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            campaign = self.campaign(root)
            foreign = root / 'foreign'
            run_batch(self.cases, foreign, ScriptedModel, variants=['P'], sources=['clean'])
            foreign_records = load_results(foreign)
            self.assertEqual(foreign_records[0]['run_id'], load_results(campaign)[0]['run_id'])
            export_review(foreign_records, campaign / 'reviews' / 'foreign')
            with self.assertRaisesRegex(ValueError, 'Review provenance differs'):
                export_campaign(campaign, root / 'rejected.zip')

    def test_interrupted_event_view_archives_explicitly_incomplete_canonical_record(self):
        from security_lab import batch
        original_write = batch._atomic_bytes
        def fail_events(path, content):
            if path.parent.name == 'events':
                raise OSError('event storage failure')
            return original_write(path, content)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            campaign = root / 'partial'
            with patch('security_lab.batch._atomic_bytes', side_effect=fail_events), self.assertRaises(OSError):
                run_batch(self.cases, campaign, ScriptedModel, variants=['B'], sources=['attack'])
            report = export_campaign(campaign, root / 'partial.zip')
            self.assertEqual(report['campaign_state'], 'interrupted')
            self.assertTrue(report['verified_integrity'])
            self.assertFalse(report['evidence_complete'])
            self.assertEqual(len(report['incomplete_event_files']), 1)
            imported = import_campaign(root / 'partial.zip', root / 'restored')
            self.assertFalse(imported['evidence_complete'])
            self.assertTrue(load_results(root / 'restored')[0]['metrics']['backend_violation'])

    def test_adjudicated_review_roundtrip_validates_all_versions_and_preserves_originals(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            campaign = self.campaign(root)
            paths, ratings, first, second = self.review_history(campaign)
            # Incomplete drafts and the untouched blank templates are valid
            # archive evidence, but cannot replace submitted original ratings.
            draft = paths['mapping'].parent / 'drafts-a' / 'draft-000001.json'
            draft.parent.mkdir()
            draft.write_text(json.dumps({'rater': '', 'ratings': []}))
            (campaign / 'summary-adjudicated.json').write_text(json.dumps(summarize(load_results(campaign))))
            original = {path.relative_to(campaign): path.read_bytes() for path in (*paths.values(), *ratings, first, second, draft)}
            report = export_campaign(campaign, root / 'reviewed.zip')
            self.assertEqual(report['verified_review_versions'], sorted(path.relative_to(campaign).as_posix() for path in (first, second)))
            imported = import_campaign(root / 'reviewed.zip', root / 'restored')
            self.assertEqual(imported['verified_review_versions'], report['verified_review_versions'])
            for relative, content in original.items():
                self.assertEqual((root / 'restored' / relative).read_bytes(), content)
            latest = json.loads((root / 'restored' / second.relative_to(campaign)).read_text())
            validate_combined(latest)
            attached = attach_reviews(load_results(root / 'restored'), latest)
            self.assertEqual(attached[0]['human_review']['status'], 'adjudicated')

    def test_corrupted_older_or_latest_combined_version_rejected_before_export(self):
        for version in (1, 2):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                campaign = self.campaign(root)
                _, _, first, second = self.review_history(campaign)
                target = first if version == 1 else second
                value = json.loads(target.read_text())
                value['judgments'][0]['original_ratings'][0]['notes'] = 'Changed after review'
                target.write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError, 'Review version integrity mismatch'):
                    export_campaign(campaign, root / 'rejected.zip')
                self.assertFalse((root / 'rejected.zip').exists())

    def test_rehashed_zip_cannot_certify_malformed_review_version(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            campaign = self.campaign(root)
            _, _, _, second = self.review_history(campaign)
            valid = root / 'valid.zip'
            export_campaign(campaign, valid)
            name = second.relative_to(campaign).as_posix()
            bad = root / 'bad.zip'
            def tamper(content):
                content[name] = b'{}'
                self.rehash_member(content, name)
            self.rewrite(valid, bad, tamper)
            with self.assertRaisesRegex(ValueError, 'Missing review version integrity'):
                verify_archive(bad)
            with self.assertRaises(ValueError):
                import_campaign(bad, root / 'rejected')
            self.assertFalse((root / 'rejected').exists())

    def test_review_inputs_and_per_judgment_mapping_are_bound_even_with_new_self_hash(self):
        for field in ('mapping_sha256', 'packets_sha256', 'packet_sha256'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                campaign = self.campaign(root)
                _, _, first, _ = self.review_history(campaign)
                value = json.loads(first.read_text())
                if field == 'packet_sha256':
                    value['judgments'][0][field] = '0' * 64
                else:
                    value[field] = '0' * 64
                self.rehash_review(value)
                validate_combined(value)  # Well-formed alone, unrelated to evidence.
                first.write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError, 'archived mapping'):
                    export_campaign(campaign, root / 'rejected.zip')

    def test_original_rating_csv_contents_and_presence_are_required(self):
        for mutation in ('embedded_original', 'missing_csv'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                campaign = self.campaign(root)
                _, ratings, first, second = self.review_history(campaign)
                second.unlink()  # A single baseline still needs authentic inputs.
                if mutation == 'missing_csv':
                    ratings[0].unlink()
                else:
                    value = json.loads(first.read_text())
                    value['judgments'][0]['original_ratings'][0]['notes'] = 'Replaced without changing the source CSV'
                    self.rehash_review(value)
                    validate_combined(value)
                    first.write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError, 'rating CSV'):
                    export_campaign(campaign, root / 'rejected.zip')

    def test_history_requires_predecessor_and_preserves_prior_ratings(self):
        for mutation in ('missing', 'changed_original'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                campaign = self.campaign(root)
                _, _, first, second = self.review_history(campaign)
                if mutation == 'missing':
                    first.unlink()
                else:
                    value = json.loads(second.read_text())
                    value['judgments'][0]['original_ratings'][0]['notes'] = 'Replaced during adjudication'
                    self.rehash_review(value)
                    validate_combined(value)
                    second.write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError, 'review history'):
                    export_campaign(campaign, root / 'rejected.zip')

    def test_cli_and_arbitrarily_named_review_versions_are_verified(self):
        for names in (('combined.json', 'adjudicated-01.json'), ('decisions-initial.json', 'decisions-final.json')):
            with self.subTest(names=names), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                campaign = self.campaign(root)
                _, _, first, second = self.review_history(campaign)
                first.rename(campaign / names[0])
                second.rename(campaign / names[1])
                report = export_campaign(campaign, root / 'valid.zip')
                self.assertEqual(report['verified_review_versions'], sorted(names))
                for payload in ('{', '{}'):
                    (campaign / names[1]).write_text(payload)
                    with self.assertRaises(ValueError):
                        export_campaign(campaign, root / 'malformed.zip')

    def test_unknown_json_cannot_silently_erase_review_role_but_opaque_non_json_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            campaign = self.campaign(root)
            extra = campaign / 'unknown.json'
            extra.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'Unrecognized JSON campaign evidence'):
                export_campaign(campaign, root / 'rejected.zip')
            extra.unlink()
            (campaign / 'notes.txt').write_text('Unclassified non-JSON research note.')
            report = export_campaign(campaign, root / 'notes.zip')
            self.assertTrue(report['verified_integrity'])
            import_campaign(root / 'notes.zip', root / 'restored')
            self.assertEqual((root / 'restored' / 'notes.txt').read_text(), 'Unclassified non-JSON research note.')
            # Import receipts and retained original archives are supported when
            # a previously imported campaign is exported again.
            self.assertTrue(export_campaign(root / 'restored', root / 'reexported.zip')['verified_integrity'])

    def test_legacy_summary_without_additive_paired_comparisons_remains_archivable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            campaign = self.campaign(root)
            path = campaign / 'summary.json'
            summary = json.loads(path.read_text())
            del summary['paired_comparisons']
            original = json.dumps(summary).encode()
            path.write_bytes(original)
            report = export_campaign(campaign, root / 'legacy-summary.zip')
            self.assertTrue(report['verified_integrity'])
            import_campaign(root / 'legacy-summary.zip', root / 'restored')
            self.assertEqual((root / 'restored' / 'summary.json').read_bytes(), original)
            summary['paired_comparisons'] = []
            path.write_text(json.dumps(summary))
            with self.assertRaisesRegex(ValueError, 'Unrecognized JSON'):
                export_campaign(campaign, root / 'invalid-summary.zip')

    def test_unindexed_uppercase_json_in_records_is_not_a_canonical_record(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            campaign = self.campaign(root)
            (campaign / 'records' / 'arbitrary-resolution.JSON').write_text('{}')
            # Windows may already reject this via case-insensitive globbing;
            # POSIX must also reject it during semantic JSON classification.
            with self.assertRaises(ValueError):
                export_campaign(campaign, root / 'rejected.zip')
