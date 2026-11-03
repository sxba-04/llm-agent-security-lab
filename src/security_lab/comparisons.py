"""Descriptive paired comparisons and repeat profiles, never pooled pseudo-tests.

Only the same case/repetition/source/model/mode can form a pair. A missing or
technically invalid partner excludes the block. Missing semantic judgments stay
pending and are never interpreted as false. No confidence intervals are claimed.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
from typing import Any

from .evaluation import METRICS, evaluate_run

CONTRASTS = (("F", "B"), ("P", "B"), ("FP", "P"), ("FP", "F"))
INPUT_FIELDS = ("original_article", "user_request", "session", "initial_tickets", "expected", "provider")
LIMIT_FIELDS = ("max_tool_calls", "max_model_calls", "timeout_seconds")
VERSION_FIELDS = ("filter_version", "policy_version")
EXECUTION_FIELDS = LIMIT_FIELDS + VERSION_FIELDS


def _input_evidence(result: dict[str, Any]) -> tuple[str | None, list[str]]:
    """Fingerprint pre-intervention evidence already present in legacy records.

    In particular article_text can contain a filter replacement and is never a
    substitute for original_article. Missing provenance cannot establish a pair.
    """
    missing = [field for field in INPUT_FIELDS
               if field not in result or not isinstance(result[field],
                   str if field in {"original_article", "user_request", "provider"} else dict)]
    if missing:
        return None, missing
    try:
        encoded = json.dumps({field: result[field] for field in INPUT_FIELDS},
                             ensure_ascii=True, sort_keys=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError):
        return None, ["invalid_input_serialization"]
    return hashlib.sha256(encoded).hexdigest(), []


def _execution_limit_value(field: str, value: Any) -> tuple[Any, bool]:
    if field != "timeout_seconds":
        return value, type(value) is int and value > 0
    try:
        valid = type(value) in (int, float) and value > 0 and math.isfinite(value)
    except OverflowError:
        valid = False
    return (float(value) if valid else value), valid


def _execution_versions(result: dict[str, Any], start: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    values, missing, invalid = {}, [], []
    for field in VERSION_FIELDS:
        if field not in result:
            missing.append(field)
        elif not isinstance(result[field], str) or not result[field].strip():
            invalid.append(field)
        else:
            values[field] = result[field]
        if field not in start:
            missing.append("run_start." + field)
        elif not isinstance(start[field], str) or not start[field].strip():
            invalid.append("run_start." + field)
        elif field in values and start[field] != values[field]:
            invalid.append(field)
    return values, missing, invalid


def _execution_limits(start: dict[str, Any], values: dict[str, Any],
                      missing: list[str], invalid: list[str]) -> None:
    limits = start.get("limits")
    if "limits" not in start:
        missing.append("limits")
    elif not isinstance(limits, dict):
        invalid.append("limits")
    else:
        for field in LIMIT_FIELDS:
            if field not in limits:
                missing.append(field)
                continue
            value = limits[field]
            value, valid = _execution_limit_value(field, value)
            if valid:
                values[field] = value
            else:
                invalid.append(field)


def _execution_evidence(result: dict[str, Any]) -> tuple[str | None, dict[str, Any], list[str], list[str]]:
    """Use recorded limits and versions, never current defaults for old runs.

    The event and top-level version labels must agree. A missing, duplicated or
    contradictory start record cannot establish identical execution conditions.
    """
    starts = [event for event in result.get("events", [])
              if isinstance(event, dict) and event.get("type") == "run_start"]
    if not starts:
        return None, {}, ["run_start"], []
    if len(starts) != 1 or not isinstance(starts[0].get("data"), dict):
        return None, {}, [], ["run_start"]
    start = starts[0]["data"]
    values, missing, invalid = _execution_versions(result, start)
    _execution_limits(start, values, missing, invalid)
    if missing or invalid:
        return None, values, missing, invalid
    encoded = json.dumps(values, ensure_ascii=True, sort_keys=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest(), values, [], []


def _metric_counts(rows: list[dict[str, Any]], metric: str, source: str) -> dict[str, Any]:
    if metric == "false_block" and source != "clean":
        return {"numerator": 0, "denominator": 0, "pending": 0,
                "not_applicable": len(rows), "rate": None}
    known = [row[metric] for row in rows if isinstance(row[metric], bool)]
    return {"numerator": sum(known), "denominator": len(known),
            "pending": len(rows) - len(known), "not_applicable": 0,
            "rate": sum(known) / len(known) if known else None}


def _index_comparison_runs(results: list[dict[str, Any]]):
    indexed: dict[tuple[Any, ...], tuple[dict[str, Any], dict[str, Any]]] = {}
    identities: dict[tuple[str, str, bool], tuple[str, str]] = {}
    cohorts: dict[tuple[str, str, str, bool], dict[tuple[str, int], dict[str, Any]]] = defaultdict(dict)
    profiles: dict[tuple[str, str, str, str, bool], list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for result in results:
        case_id = str(result.get("case_id", ""))
        repetition = result.get("repetition", 1)
        if not case_id or type(repetition) is not int or repetition < 1:
            raise ValueError("Paired comparisons require a case identity and positive repetition")
        variant, source = str(result.get("variant", "")), str(result.get("source", ""))
        if variant not in {"B", "F", "P", "FP"} or source not in {"clean", "attack"}:
            raise ValueError("Paired comparisons require a known variant and source")
        model, mode = str(result.get("model", "unknown")), bool(result.get("is_mock"))
        goal, scenario = str(result.get("goal", "")), str(result.get("scenario_group", ""))
        identity = (case_id, model, mode)
        if identity in identities and identities[identity] != (goal, scenario):
            raise ValueError("Case goal or scenario group differs within one comparison")
        identities[identity] = (goal, scenario)
        natural_key = (case_id, repetition, variant, source, model, mode)
        if natural_key in indexed:
            raise ValueError("Duplicate case/repetition/condition: refusing ambiguous pairs")
        metrics = evaluate_run(result)
        indexed[natural_key] = (result, metrics)
        cohorts[(source, goal, model, mode)].setdefault((case_id, repetition), {})[variant] = (result, metrics)
        profiles[(case_id, variant, source, model, mode)].append((result, metrics))

    return identities, cohorts, profiles


def _compare_input_evidence(left_record, right_record, reasons):
    left_hash, left_missing = _input_evidence(left_record)
    right_hash, right_missing = _input_evidence(right_record)
    evidence = {"input_fingerprints": {"left": left_hash, "right": right_hash},
                "missing_input_fields": {"left": left_missing, "right": right_missing}}
    if left_missing or right_missing:
        reasons.append("missing_input_evidence")
    elif left_hash != right_hash:
        reasons.append("input_mismatch")
        evidence["mismatch_fields"] = [field for field in INPUT_FIELDS
                                        if left_record[field] != right_record[field]]
    return evidence


def _compare_execution_evidence(left_record, right_record, reasons, evidence):
    left_execution, left_values, left_missing, left_invalid = _execution_evidence(left_record)
    right_execution, right_values, right_missing, right_invalid = _execution_evidence(right_record)
    evidence.update({
        "execution_fingerprints": {"left": left_execution, "right": right_execution},
        "missing_execution_fields": {"left": left_missing, "right": right_missing},
        "invalid_execution_fields": {"left": left_invalid, "right": right_invalid},
    })
    if left_missing or right_missing:
        reasons.append("missing_execution_evidence")
    if left_invalid or right_invalid:
        reasons.append("invalid_execution_evidence")
    if left_execution and right_execution and left_execution != right_execution:
        reasons.append("execution_mismatch")
        evidence["mismatch_execution_fields"] = [field for field in EXECUTION_FIELDS
                                                  if left_values[field] != right_values[field]]


def _pair_exclusions(block, left: str, right: str):
    reasons = []
    evidence = {}
    for side, variant in (("left", left), ("right", right)):
        if variant not in block:
            reasons.append("missing_" + side)
        elif not block[variant][1]["valid_for_rates"]:
            reasons.append("invalid_" + side)
    if left in block and right in block:
        left_record, right_record = block[left][0], block[right][0]
        evidence = _compare_input_evidence(left_record, right_record, reasons)
        _compare_execution_evidence(left_record, right_record, reasons, evidence)
    return reasons, evidence


def _paired_metrics(pairs, source: str) -> dict[str, Any]:
    metric_rows = {}
    for metric in METRICS:
        applicable = metric != "false_block" or source == "clean"
        known = [(a[metric], b[metric]) for a, b in pairs
                 if applicable and isinstance(a[metric], bool) and isinstance(b[metric], bool)]
        left_numerator, right_numerator = sum(a for a, _ in known), sum(b for _, b in known)
        denominator = len(known)
        metric_rows[metric] = {
            "left_numerator": left_numerator, "right_numerator": right_numerator,
            "denominator": denominator,
            "pending": len(pairs) - denominator if applicable else 0,
            "not_applicable": 0 if applicable else len(pairs),
            "left_rate": left_numerator / denominator if denominator else None,
            "right_rate": right_numerator / denominator if denominator else None,
            "difference_pp": 100 * (left_numerator - right_numerator) / denominator if denominator else None,
        }
    return metric_rows


def _compare_contrast(relevant, identities, cohort: tuple[str, str, str, bool],
                      left: str, right: str) -> dict[str, Any]:
    source, goal, model, mode = cohort
    excluded_counts = dict.fromkeys(("missing_left", "missing_right", "invalid_left", "invalid_right",
                                     "input_mismatch", "missing_input_evidence", "execution_mismatch",
                                     "missing_execution_evidence", "invalid_execution_evidence"), 0)
    excluded_blocks = []
    pairs = []
    for (case_id, repetition), block in sorted(relevant.items()):
        reasons, evidence = _pair_exclusions(block, left, right)
        if reasons:
            for reason in reasons:
                excluded_counts[reason] += 1
            excluded_blocks.append({"case_id": case_id,
                                    "scenario_group": identities[(case_id, model, mode)][1],
                                    "repetition": repetition, "reasons": reasons, **evidence})
        else:
            pairs.append((block[left][1], block[right][1]))
    metric_rows = _paired_metrics(pairs, source)
    return {
        "comparison": f"{left}-{right}", "left_variant": left, "right_variant": right,
        "source": source, "goal": goal, "model": model, "engineering_only": mode,
        "n_candidate_blocks": len(relevant), "n_common_valid_blocks": len(pairs),
        "n_excluded_blocks": len(excluded_blocks), "excluded": excluded_counts,
        "excluded_blocks": excluded_blocks, "metrics": metric_rows,
    }


def _case_profiles(profiles, identities) -> list[dict[str, Any]]:
    case_profiles = []
    for (case_id, variant, source, model, mode), rows in sorted(profiles.items()):
        rows.sort(key=lambda item: item[0].get("repetition", 1))
        valid = [metrics for _, metrics in rows if metrics["valid_for_rates"]]
        goal, scenario = identities[(case_id, model, mode)]
        case_profiles.append({
            "case_id": case_id, "scenario_group": scenario, "goal": goal,
            "variant": variant, "source": source, "model": model, "engineering_only": mode,
            "n_runs": len(rows), "n_valid": len(valid), "n_invalid": len(rows) - len(valid),
            "repetitions": [result.get("repetition", 1) for result, _ in rows],
            "metrics": {metric: _metric_counts(valid, metric, source) for metric in METRICS},
            "outcomes": [{"repetition": result.get("repetition", 1), "status": result.get("status"),
                          "valid_for_rates": metrics["valid_for_rates"],
                          "metrics": {metric: metrics[metric] for metric in METRICS}}
                         for result, metrics in rows],
        })
    return case_profiles


def paired_comparisons(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Return differences in percentage points and per-case repeat profiles.

    Each metric uses only pairs with two known judgments. Exclusion counts may
    overlap by reason; n_excluded_blocks counts each excluded block only once.
    Case profiles preserve raw repeat outcomes and scenario-group identities.
    """
    identities, cohorts, profiles = _index_comparison_runs(results)
    comparisons = []
    for cohort, blocks in sorted(cohorts.items()):
        for left, right in CONTRASTS:
            relevant = {key: block for key, block in blocks.items() if left in block or right in block}
            if relevant:
                comparisons.append(_compare_contrast(relevant, identities, cohort, left, right))
    case_profiles = _case_profiles(profiles, identities)
    return {"schema_version": 1, "difference": "left_minus_right_percentage_points",
            "input_fingerprint_fields": list(INPUT_FIELDS),
            "execution_fingerprint_fields": list(EXECUTION_FIELDS),
            "legacy_execution_evidence": "Runs without recorded limits and consistent filter/policy versions remain in case profiles but are excluded from paired comparisons; current defaults are never substituted.",
            "interpretation": "Descriptive paired differences require identical original input, permissions, initial state, rubric, provider, execution limits and filter/policy versions. Repeats remain grouped within cases. Pending judgments are excluded metric by metric. No confidence intervals or independence claims.",
            "comparisons": comparisons, "case_profiles": case_profiles}
