import hashlib
import copy
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
from security_lab.review import export_review


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
