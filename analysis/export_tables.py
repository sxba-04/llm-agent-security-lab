"""Export summary metric counts as a CSV; values remain pending until reviewed.

Usage: python analysis/export_tables.py runs/pilot/summary.json runs/pilot/table.csv
"""
import csv
import json
from pathlib import Path
import sys


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: export_tables.py SUMMARY.json TABLE.csv")
    summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2])
    if out.exists():
        raise SystemExit("Output already exists; choose a new version")
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = ["engineering_only", "variant", "source", "goal", "model", "metric", "numerator", "denominator", "pending", "not_applicable", "rate"]
    with out.open("x", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for group in summary["groups"]:
            for metric, values in group["metrics"].items():
                writer.writerow({"engineering_only": group["engineering_only"],
                                 **{key: group.get(key) for key in ("variant", "source", "goal", "model")},
                                 "metric": metric, **values})


if __name__ == "__main__":
    main()
