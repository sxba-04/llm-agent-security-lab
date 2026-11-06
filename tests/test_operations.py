from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from security_lab.operations import storage_status


class StorageStatusTests(unittest.TestCase):
    def test_low_space_thresholds_and_normal_capacity(self):
        for total, free, expected in [
            (1024**3, 100 * 1024**2, "low"),
            (100 * 1024**3, 10 * 1024**3, "low"),
            (1024**3, 300 * 1024**2, "ok"),
        ]:
            with self.subTest(total=total, free=free), patch(
                "security_lab.operations.shutil.disk_usage",
                return_value=SimpleNamespace(total=total, free=free),
            ):
                result = storage_status(Path("private-workspace"))
                self.assertEqual(result, {"state": expected, "total_bytes": total,
                                          "free_bytes": free})

    def test_capacity_failure_is_explicit_and_reveals_no_path(self):
        with patch("security_lab.operations.shutil.disk_usage",
                   side_effect=OSError("private-workspace is inaccessible")):
            self.assertEqual(storage_status(Path("private-workspace")),
                             {"state": "unknown", "total_bytes": None, "free_bytes": None})

    def test_invalid_capacity_is_not_reported_as_healthy(self):
        with patch("security_lab.operations.shutil.disk_usage",
                   return_value=SimpleNamespace(total=0, free=0)):
            self.assertEqual(storage_status(Path("."))["state"], "unknown")
