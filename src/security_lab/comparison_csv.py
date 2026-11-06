"""Spreadsheet-safe exports of the same descriptive summary shown in the UI."""
from __future__ import annotations

import csv
import io
import json
from typing import Any

from .evaluation import METRICS

FIELDS = ["row_type", "campaign_id", "display_name", "review_set_id", "metric", "variant", "comparison",
          "case_id", "source", "goal", "model", "engineering_only", "n_runs", "n_valid", "n_invalid",
          "n_base_cases", "repetitions", "numerator", "denominator", "pending", "not_applicable", "rate",
          "left_numerator", "right_numerator", "left_rate", "right_rate", "difference_pp",
          "n_candidate_blocks", "n_common_valid_blocks", "n_excluded_blocks", "excluded", "excluded_blocks"]


def _cell(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    # csv quoting alone does not stop a spreadsheet from executing formulas.
    # Numeric values stay numeric, including negative paired differences.
    if isinstance(value, str) and (value.lstrip().startswith(("=", "+", "-", "@"))
                                   or value.startswith(("\t", "\r", "\n"))):
        return "'" + value
    return value


def comparison_csv(summary: dict[str, Any], campaign_id: str, *, display_name: str = "",
                   review_set_id: str = "", metric: str = "", source: str = "", goal: str = "") -> str:
    if metric and metric not in METRICS:
        raise ValueError("Unbekannte Messgröße.")
    if source not in {"", "clean", "attack"}:
        raise ValueError("Unbekannte Quellbedingung.")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    paired = summary.get("paired_comparisons", {})
    for kind, rows in (("group", summary["groups"]), ("pair", paired.get("comparisons", [])),
                       ("case", paired.get("case_profiles", []))):
        for row in rows:
            if (source and row["source"] != source) or (goal and row["goal"] != goal):
                continue
            for name, counts in row["metrics"].items():
                if metric and metric != name:
                    continue
                identity = {key: row[key] for key in FIELDS if key in row}
                values = {**identity, **{key: counts[key] for key in FIELDS if key in counts},
                          "row_type": kind, "campaign_id": campaign_id, "display_name": display_name,
                          "review_set_id": review_set_id, "metric": name}
                writer.writerow({key: _cell(value) for key, value in values.items()})
    return stream.getvalue()
