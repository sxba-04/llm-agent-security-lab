from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest

from security_lab.budget import BudgetLedger
from security_lab.contracts import BudgetExceeded


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'budget.json'

    def test_pending_requests_and_restart_count_against_cap(self):
        ledger = BudgetLedger(self.path, 1, 1)
        first = ledger.reserve('0.7')
        with self.assertRaises(BudgetExceeded):
            BudgetLedger(self.path, 1, 1).reserve('0.4')
        ledger.settle(first, '0.2')
        ledger.reserve('0.8')
        self.assertEqual(ledger.snapshot()['accounted_eur'], '1.0')

    def test_overrun_is_preserved_and_halts_future_requests(self):
        ledger = BudgetLedger(self.path, 5, 1)
        entry = ledger.reserve('0.5')
        self.assertFalse(ledger.settle(entry, '0.8'))
        self.assertEqual(ledger.snapshot()['accounted_eur'], '0.8')
        with self.assertRaises(BudgetExceeded):
            BudgetLedger(self.path, 5, 1).reserve('0.1')

    def test_reservation_cannot_be_settled_twice(self):
        ledger = BudgetLedger(self.path, 1, 1)
        entry = ledger.reserve('0.5')
        ledger.settle(entry, '0.1')
        with self.assertRaises(BudgetExceeded):
            ledger.settle(entry, 0)

    def test_corruption_and_existing_lock_fail_closed(self):
        self.path.write_text('{bad json', encoding='utf-8')
        ledger = BudgetLedger(self.path, 1, 1)
        with self.assertRaises(BudgetExceeded):
            ledger.reserve('0.1')
        self.assertFalse(ledger.lock_path.exists())
        ledger.lock_path.write_text('interrupted process', encoding='utf-8')
        with self.assertRaises(BudgetExceeded):
            ledger.reserve('0.1')
        self.assertTrue(ledger.lock_path.exists())

    def test_parallel_reservations_never_exceed_cap(self):
        def attempt(_):
            try:
                BudgetLedger(self.path, 1, 1).reserve('0.4')
                return True
            except BudgetExceeded:
                return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            success = sum(pool.map(attempt, range(20)))
        self.assertLessEqual(success, 2)
        self.assertEqual(float(BudgetLedger(self.path, 1, 1).snapshot()['accounted_eur']), success * 0.4)

    def test_invalid_amounts_or_project_cap_rejected(self):
        for invalid in (251, float('nan'), float('inf'), 0, -1, True):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                BudgetLedger(self.path, invalid)
        ledger = BudgetLedger(self.path)
        for invalid in (float('nan'), 0, -1, True):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                ledger.reserve(invalid)
        self.assertFalse(self.path.exists())

    def test_per_request_ceiling_enforced_before_file_creation(self):
        ledger = BudgetLedger(self.path, 10, '0.1')
        with self.assertRaises(BudgetExceeded):
            ledger.reserve('0.11')
        self.assertFalse(self.path.exists())


if __name__ == '__main__':
    unittest.main()
