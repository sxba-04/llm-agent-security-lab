import copy
import json
from pathlib import Path
import tempfile
import unittest

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
