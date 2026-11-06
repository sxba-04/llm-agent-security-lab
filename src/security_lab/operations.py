"""Small read-only operational signals for the authenticated workbench."""
from pathlib import Path
import shutil


def storage_status(workspace: Path) -> dict:
    """Report filesystem capacity, not an assertion about disk persistence.

    No filenames or server paths leave this boundary. A failed capacity query
    must not prevent health checks, backups or recovery of existing evidence.
    """
    try:
        usage = shutil.disk_usage(workspace)
        if usage.total <= 0 or usage.free < 0 or usage.free > usage.total:
            raise ValueError("Invalid filesystem capacity")
    except (OSError, ValueError):
        return {"state": "unknown", "total_bytes": None, "free_bytes": None}
    low = usage.free <= max(100 * 1024 * 1024, usage.total // 10)
    return {"state": "low" if low else "ok", "total_bytes": usage.total,
            "free_bytes": usage.free}
