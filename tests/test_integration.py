import contextlib
import copy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from security_lab.batch import load_results, run_batch
from security_lab.cases import load_cases
from security_lab.cli import main
from security_lab.contracts import ModelError, ModelReply, ToolCall
from security_lab.core import run_case
from security_lab.models import ScriptedModel


ROOT = Path(__file__).parents[1]


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_cases(ROOT / 'cases/dev')

    def test_paid_calls_require_both_explicit_gates(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            for flags in ([], ['--allow-paid-api'], ['--isolation-acknowledged']):
                status = main(['run', '--cases', str(ROOT/'cases/dev'), '--provider', 'openai',
                               '--output', str(Path(tmp)/'campaign'), *flags])
                self.assertEqual(status, 2)
                self.assertFalse((Path(tmp)/'campaign').exists())

    def test_human_reviews_reach_summary_without_changing_originals(self):
        from security_lab.review import export_review, combine_reviews
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'campaign'
            g3 = next(c for c in self.cases if c['goal'] == 'G3')
            run_batch([g3], out, lambda c,s: ScriptedModel(c,s), variants=['P'], sources=['attack'])
            originals = load_results(out)
            exported = export_review(originals, Path(tmp)/'review')
            for name, rater in [('ratings_a','test-rater-a'),('ratings_b','test-rater-b')]:
                path = Path(exported[name])
                with path.open(newline='', encoding='utf-8') as stream:
                    reader = csv.DictReader(stream)
                    fields = reader.fieldnames
                    rows = list(reader)
                for row in rows:
                    row.update(rater=rater, legitimate_rating='partial', attack_success='yes', notes='Synthetic test rating')
                    if 'false_block' in row:
                        row['false_block'] = 'no'
                with path.open('w', newline='', encoding='utf-8') as stream:
                    writer = csv.DictWriter(stream, fieldnames=fields)
                    writer.writeheader(); writer.writerows(rows)
            combined = Path(tmp)/'combined.json'
            combine_reviews(exported['mapping'], [exported['ratings_a'],exported['ratings_b']], combined)
            summary_path = Path(tmp)/'summary.json'
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['summarize', str(out), '--reviews', str(combined), '--output', str(summary_path)]), 0)
            summary = json.loads(summary_path.read_text())
            metric = summary['groups'][0]['metrics']['attacker_goal']
            self.assertEqual((metric['numerator'],metric['denominator']), (1,1))
            self.assertEqual(load_results(out), originals)

    def test_post_response_errors_preserve_exposure_and_stop_tool_effects(self):
        case = copy.deepcopy(next(c for c in self.cases if c['goal'] == 'G1'))
        target = case['expected']['target_ticket_id']
        for flag in ('model_version_changed', 'accounting_error'):
            class Model:
                name = 'test-model'; is_mock = False
                n = 0
                def respond(self, messages, tools):
                    self.n += 1
                    if self.n == 1:
                        return ModelReply(tool_calls=[ToolCall('read_ticket', {'ticket_id':target})], finish_reason='tool_calls')
                    return ModelReply(tool_calls=[ToolCall('append_note', {'ticket_id':target, 'text':'must not execute'})],
                                      usage={flag:True,'model':'changed-model'}, finish_reason='tool_calls')
            result = run_case(case, 'B', 'attack', Model())
            self.assertEqual(result['status'], 'technical_error')
            kinds = [e['type'] for e in result['events']]
            self.assertIn('context_exposure', kinds)
            self.assertNotIn('backend_write', kinds)
            self.assertIn('changed-model', result['observed_models'])

    def test_truncated_tool_response_is_not_executed(self):
        case = self.cases[0]
        class Model:
            name='test'; is_mock=False
            def respond(self, messages, tools):
                return ModelReply(tool_calls=[ToolCall('read_ticket', {'ticket_id':case['expected']['target_ticket_id']})], finish_reason='length')
        result = run_case(case, 'B', 'attack', Model())
        self.assertEqual(result['status'], 'limit_exceeded')
        self.assertTrue(any(e['type']=='proposal' for e in result['events']))
        self.assertFalse(any(e['type']=='backend_read' for e in result['events']))

    def test_campaign_stops_after_provider_failure(self):
        class Model:
            name='broken-test'; is_mock=False
            def respond(self, messages, tools):
                raise ModelError('not logged')
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'campaign'
            result=run_batch(self.cases[:1],out,lambda c,s: Model(),variants=['B','P'],sources=['clean','attack'])
            self.assertEqual(result['state'],'stopped')
            self.assertEqual(result['completed_runs'],1)
            self.assertEqual(result['planned_runs'],4)
            self.assertEqual(load_results(out)[0]['status'],'technical_error')
