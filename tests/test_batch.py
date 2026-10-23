import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from security_lab.batch import load_results, run_batch, schedule
from security_lab.cases import load_cases
from security_lab.models import ScriptedModel


class BatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_cases(Path(__file__).parents[1] / "cases/dev")

    def test_paired_schedule_reproducible_complete(self):
        order = schedule(self.cases, ["B", "F", "P", "FP"], ["clean", "attack"], 3, 42)
        self.assertEqual(len(order), len(self.cases) * 24)
        self.assertEqual(order, schedule(self.cases, ["B", "F", "P", "FP"], ["clean", "attack"], 3, 42))
        self.assertNotEqual(order, schedule(self.cases, ["B", "F", "P", "FP"], ["clean", "attack"], 3, 43))
        for start in range(0, len(order), 8):
            block = order[start:start+8]
            self.assertEqual(len({(e['variant'], e['source']) for e in block}), 8)
            self.assertEqual(len({(e['case_id'], e['repetition']) for e in block}), 1)

    def test_campaign_reset_hash_checks_and_no_overwrite(self):
        cases = copy.deepcopy(self.cases[:1])
        original = copy.deepcopy(cases)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "campaign"
            result = run_batch(cases, out, lambda c,s: ScriptedModel(c,s), variants=["B","P"], sources=["clean","attack"])
            self.assertEqual(result['state'], 'completed')
            self.assertEqual(len(load_results(out)), 4)
            self.assertEqual(cases, original)
            with self.assertRaises(FileExistsError):
                run_batch(cases, out, lambda c,s: ScriptedModel(c,s), variants=["B"], sources=["clean"])
            record = out / result['runs'][0]['path']
            changed = json.loads(record.read_text())
            changed['final_text'] = 'tampered'
            record.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                load_results(out)

    def test_schedule_rejects_duplicate_conditions(self):
        with self.assertRaises(ValueError):
            schedule(self.cases, ['B','B'], ['clean'], 1, 1)

    def test_cancel_before_first_run_preserves_empty_campaign(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'cancelled'
            snapshots = []
            def factory(*args):
                self.fail('Cancelled batch must not construct a model')
            result = run_batch(self.cases[:1], out, factory, variants=['B'], sources=['clean'],
                               should_cancel=lambda: True, on_progress=snapshots.append)
            self.assertEqual(result['state'], 'cancelled')
            self.assertEqual(result['completed_runs'], 0)
            self.assertEqual(load_results(out), [])
            self.assertEqual(snapshots[-1]['state'], 'cancelled')
            self.assertEqual(json.loads((out/'summary.json').read_text())['campaign_state'], 'cancelled')

    def test_cancel_after_a_completed_run_and_detached_progress(self):
        stop = False
        seen = []
        def progress(manifest):
            nonlocal stop
            seen.append(manifest['completed_runs'])
            if manifest['completed_runs']:
                stop = True
            manifest['runs'].clear()  # Cannot mutate the runner's manifest.
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'partial'
            result = run_batch(self.cases[:1], out, ScriptedModel, variants=['B','P'], sources=['clean'],
                               should_cancel=lambda: stop, on_progress=progress)
            self.assertEqual(result['state'], 'cancelled')
            self.assertEqual(len(load_results(out)), 1)
            self.assertEqual(result['completed_runs'], 1)
            self.assertEqual(result['planned_runs'], 2)
            self.assertEqual(seen[0], 0)

    def test_cancel_current_run_preserves_partial_evidence(self):
        from security_lab.contracts import ModelReply, ToolCall
        stop = False
        class CancelModel:
            name = 'cancel-test'
            is_mock = True
            def respond(self, messages, tools):
                nonlocal stop
                stop = True
                return ModelReply(tool_calls=[ToolCall('read_ticket', {'ticket_id':'A17'})])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'cancel-current'
            manifest = run_batch(self.cases[:1], out, lambda *_: CancelModel(), variants=['B'], sources=['clean'],
                                 should_cancel=lambda: stop)
            records = load_results(out)
            self.assertEqual(manifest['state'], 'cancelled')
            self.assertEqual(records[0]['status'], 'cancelled')
            self.assertFalse(records[0]['metrics']['valid_for_rates'])
            self.assertFalse(any(e['type']=='backend_read' for e in records[0]['events']))

    def test_events_have_hash_and_legacy_cross_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'events'
            manifest=run_batch(self.cases[:1],out,ScriptedModel,variants=['B'],sources=['clean'])
            event_path=out/manifest['runs'][0]['events_path']
            original=event_path.read_bytes()
            event_path.write_bytes(original+b'\n')
            with self.assertRaisesRegex(ValueError,'Event file hash mismatch'):
                load_results(out)
            event_path.write_bytes(original)
            manifest['schema_version']=1
            del manifest['runs'][0]['events_path']
            del manifest['runs'][0]['events_sha256']
            (out/'manifest.json').write_text(json.dumps(manifest))
            self.assertEqual(len(load_results(out)),1)
            lines=original.decode().splitlines()
            event=json.loads(lines[0]); event['type']='tampered'
            lines[0]=json.dumps(event)
            event_path.write_text('\n'.join(lines)+'\n')
            with self.assertRaisesRegex(ValueError,'Event evidence differs'):
                load_results(out)

    def test_completed_manifest_cannot_claim_missing_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'missing'
            manifest=run_batch(self.cases[:1],out,ScriptedModel,variants=['B'],sources=['clean'])
            manifest['runs']=[]
            manifest['completed_runs']=0
            (out/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'missing runs'):
                load_results(out)

    def test_factory_exception_preserves_progress(self):
        calls=0
        def factory(case,source):
            nonlocal calls
            calls+=1
            if calls==2:
                raise RuntimeError('simulation')
            return ScriptedModel(case,source)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'interrupted'
            with self.assertRaisesRegex(RuntimeError,'simulation'):
                run_batch(self.cases[:1],out,factory,variants=['B','P'],sources=['clean'])
            manifest=json.loads((out/'manifest.json').read_text())
            self.assertEqual(manifest['state'],'interrupted')
            self.assertEqual(manifest['completed_runs'],1)
            self.assertEqual(len(load_results(out)),1)

    def test_json_writes_preserve_surrogates_and_reject_nonfinite(self):
        from security_lab.batch import digest,write_json
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'evidence.json'
            value={'text':'before\ud800after'}
            write_json(path,value)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')),value)
            self.assertEqual(digest(json.loads(path.read_text())),digest(value))
            with self.assertRaises(ValueError):
                write_json(path,{'cost':float('nan')})
            self.assertEqual(json.loads(path.read_text()),value)

    def test_failed_derived_event_write_preserves_canonical_evidence(self):
        from security_lab import batch
        original_write = batch._atomic_bytes
        def fail_events(path, content):
            if path.parent.name == 'events':
                raise OSError('simulated event storage failure')
            return original_write(path, content)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'interrupted-events'
            with patch('security_lab.batch._atomic_bytes', side_effect=fail_events), self.assertRaises(OSError):
                run_batch(self.cases[:1], out, ScriptedModel, variants=['B'], sources=['attack'])
            manifest = json.loads((out / 'manifest.json').read_text())
            self.assertEqual(manifest['state'], 'interrupted')
            self.assertEqual(manifest['completed_runs'], 1)
            self.assertEqual(manifest['runs'][0]['events_state'], 'failed')
            records = load_results(out)
            self.assertEqual(len(records), 1)
            self.assertTrue(records[0]['metrics']['backend_violation'])
            self.assertTrue(any(event['type'] == 'backend_read' for event in records[0]['events']))
            summary = json.loads((out / 'summary.json').read_text())
            self.assertFalse(summary['evidence_complete'])
            self.assertEqual(len(summary['incomplete_event_files']), 1)
            # Once an event view exists it must be checked, even if its prior
            # write failed. The marker must never excuse changed evidence.
            event = out / manifest['runs'][0]['events_path']
            event.parent.mkdir(exist_ok=True)
            event.write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'Event file hash mismatch'):
                load_results(out)

    def test_legacy_jsonl_accepts_literal_unicode_line_separators(self):
        case = copy.deepcopy(self.cases[0])
        case['mock']['clean'][-1]['text'] += '\u2028paragraph\u2029next\u0085end'
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'legacy-unicode'
            manifest = run_batch([case], out, ScriptedModel, variants=['B'], sources=['clean'])
            record = load_results(out)[0]
            event_path = out / manifest['runs'][0]['events_path']
            event_path.write_text(''.join(json.dumps(event, ensure_ascii=False) + '\n' for event in record['events']), encoding='utf-8')
            manifest['schema_version'] = 1
            del manifest['runs'][0]['events_sha256']
            del manifest['runs'][0]['events_state']
            (out / 'manifest.json').write_text(json.dumps(manifest))
            self.assertEqual(load_results(out), [record])
