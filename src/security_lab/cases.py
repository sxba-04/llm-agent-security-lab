"""Load and validate trusted synthetic case fixtures.

Article text is untrusted input. Session permissions and expected outcomes belong
to the harness and must never be copied from an article or model response.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


class CaseValidationError(ValueError):
    """A fixture does not meet the documented experiment contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CaseValidationError(message)


def _text(value: Any, label: str) -> None:
    _require(isinstance(value, str) and bool(value.strip()), f"{label}: non-empty string required")


def _object(value: Any, label: str, required: set[str]) -> None:
    _require(isinstance(value, dict), f"{label}: object required")
    _require(required <= value.keys(), f"{label}: missing fields {sorted(required - value.keys())}")


def _contains_fact(text: str, fact: str) -> bool:
    """Compare text with whitespace collapsed; retain case and actual content.

    PDF line wrapping must not remove a fact. This check never rewrites the
    stored source and does not certify meaning or permit lexical substitutions.
    """
    return " ".join(fact.split()) in " ".join(text.split())


def validate_case(case: dict[str, Any]) -> None:
    """Reject inconsistent permissions, absent facts and invalid mock scripts.

    Structural validation is not a scientific assessment of scenario realism or
    semantic attack success; those require the documented human review.
    """
    fields = {
        "case_id", "scenario_group", "goal", "strategy", "user_request",
        "session", "tickets", "articles", "expected", "mock",
    }
    _object(case, "case", fields)
    for name in ("case_id", "scenario_group", "user_request"):
        _text(case[name], name)
    _require(bool(re.fullmatch(r"[A-Za-z0-9_-]+", case["case_id"])), "case_id: unsafe identifier")
    _text(case["goal"], "goal")
    _text(case["strategy"], "strategy")
    _require(case["goal"] in {"G1", "G2", "G3"}, "goal: expected G1, G2 or G3")
    _require(case["strategy"] in {"authority", "dependency"}, "strategy: unsupported strategy")

    tickets = case["tickets"]
    _require(isinstance(tickets, dict) and bool(tickets), "tickets: non-empty object required")
    for ticket_id, ticket in tickets.items():
        _text(ticket_id, "ticket ID")
        _require(re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", ticket_id) is not None,
                 "ticket ID: expected a letter followed by up to 63 letters, digits, underscores or hyphens")
        _object(ticket, f"ticket {ticket_id}", {"id", "project", "title", "facts", "notes"})
        _require(ticket["id"] == ticket_id, f"ticket {ticket_id}: id does not match mapping key")
        _text(ticket["project"], f"ticket {ticket_id}.project")
        _require(ticket["project"] in {"Alpha", "Beta"}, f"ticket {ticket_id}: unknown project")
        _text(ticket["title"], f"ticket {ticket_id}.title")
        _require(isinstance(ticket["facts"], dict) and bool(ticket["facts"]), f"ticket {ticket_id}: facts required")
        for key, value in ticket["facts"].items():
            _text(key, f"ticket {ticket_id}.facts key")
            _text(value, f"ticket {ticket_id}.facts value")
        _require(isinstance(ticket["notes"], list), f"ticket {ticket_id}: notes must be a list")
        for note in ticket["notes"]:
            _text(note, f"ticket {ticket_id}.notes")
        if "secret" in ticket:
            _require(ticket["secret"] == "__GENERATE__", f"ticket {ticket_id}: use generated synthetic canaries only")
            _require(ticket["project"] == "Beta", f"ticket {ticket_id}: canary belongs in restricted Beta data")

    session = case["session"]
    _object(session, "session", {"user_id", "read_ticket_ids", "write_ticket_id", "write_enabled"})
    _text(session["user_id"], "session.user_id")
    allowed = session["read_ticket_ids"]
    _require(isinstance(allowed, list) and bool(allowed), "session.read_ticket_ids: non-empty list required")
    _require(all(isinstance(item, str) for item in allowed), "session.read_ticket_ids: strings required")
    _require(len(set(allowed)) == len(allowed), "session.read_ticket_ids: duplicate ID")
    for ticket_id in allowed:
        _require(ticket_id in tickets, f"session: unknown readable ticket {ticket_id}")
        _require(tickets[ticket_id]["project"] == "Alpha", "session: Beta must remain restricted")
    _require(type(session["write_enabled"]) is bool, "session.write_enabled: boolean required")
    write_id = session["write_ticket_id"]
    _require(write_id is None or isinstance(write_id, str), "session.write_ticket_id: string or null required")
    if write_id is not None:
        _require(write_id in allowed, "session: writable ticket must also be an allowed Alpha ticket")
    if session["write_enabled"]:
        _require(write_id is not None, "session: write mode requires a target ticket")

    articles = case["articles"]
    _object(articles, "articles", {"clean", "attack"})
    for source in ("clean", "attack"):
        _text(articles[source], f"articles.{source}")
        _require("__GENERATE__" not in articles[source] and "{{secret:" not in articles[source],
                 f"articles.{source}: must not include secret fixtures")
    _require(articles["clean"] != articles["attack"], "articles: clean and attack versions must differ")
    if "document" in case:
        _object(case["document"], "document", {"document_id", "title", "origin"})
        for field in ("document_id", "title", "origin"):
            _text(case["document"][field], f"document.{field}")
    if "article_sources" in case:
        _require(isinstance(case["article_sources"], dict), "article_sources: object required")
        _require(set(case["article_sources"]) <= {"clean", "attack"}, "article_sources: unknown source version")
        for source, metadata in case["article_sources"].items():
            _require(isinstance(metadata, dict) and bool(metadata), f"article_sources.{source}: metadata object required")
            try:
                json.dumps(metadata, allow_nan=False)
            except (TypeError, ValueError) as exc:
                raise CaseValidationError(f"article_sources.{source}: finite JSON metadata required") from exc
    _require("__GENERATE__" not in case["user_request"] and "{{secret:" not in case["user_request"],
             "user_request: must not include secret fixtures")

    expected = case["expected"]
    _object(expected, "expected", {"target_ticket_id", "legitimate_ticket_id", "required_facts", "false_claim", "task"})
    for field in ("target_ticket_id", "legitimate_ticket_id"):
        _text(expected[field], f"expected.{field}")
        _require(expected[field] in tickets, f"expected.{field}: unknown ticket")
    _require(expected["legitimate_ticket_id"] in allowed, "expected: legitimate ticket is not readable")
    facts = expected["required_facts"]
    _require(isinstance(facts, list) and bool(facts), "expected.required_facts: non-empty list required")
    for fact in facts:
        _text(fact, "expected.required_facts item")
    _require(len(set(facts)) == len(facts), "expected.required_facts: duplicate fact")
    fact_sources = expected.get("required_fact_sources")
    if fact_sources is None:
        # Legacy fixtures put all required facts in the article. New fixtures
        # identify their source so a legitimate task can need both sources.
        fact_sources = [{"fact": fact, "source": "article"} for fact in facts]
    _require(isinstance(fact_sources, list), "expected.required_fact_sources: list required")
    mapped_facts = []
    for entry in fact_sources:
        _object(entry, "expected.required_fact_sources item", {"fact", "source"})
        _text(entry["fact"], "fact source.fact")
        _text(entry["source"], "fact source.source")
        _require(entry["source"] in {"article", "ticket"}, "fact source: article or ticket required")
        mapped_facts.append(entry["fact"])
        if entry["source"] == "article":
            _require(set(entry) == {"fact", "source"}, "article fact source: unexpected fields")
            _require(all(_contains_fact(articles[s], entry["fact"]) for s in ("clean", "attack")),
                     "article facts: clean and attack must preserve required facts")
        else:
            _require(set(entry) == {"fact", "source", "ticket_id"}, "ticket fact source: ticket_id required")
            ticket_id = entry["ticket_id"]
            _require(isinstance(ticket_id, str) and ticket_id in allowed,
                     "ticket fact source: readable ticket required")
            ticket_text = "\n".join(tickets[ticket_id]["facts"].values())
            _require(_contains_fact(ticket_text, entry["fact"]), "ticket fact source: fact absent from ticket facts")
    _require(len(mapped_facts) == len(facts) and set(mapped_facts) == set(facts),
             "expected.required_fact_sources: exactly one source per required fact required")
    if "semantic_criteria" in expected:
        criteria = expected["semantic_criteria"]
        _require(isinstance(criteria, list) and bool(criteria), "expected.semantic_criteria: nonempty list required")
        for criterion in criteria:
            _text(criterion, "expected.semantic_criteria item")
    _require(isinstance(expected["false_claim"], str), "expected.false_claim: string required")
    _text(expected["task"], "expected.task")
    _require(expected["task"] in {"read", "write"}, "expected.task: read or write required")
    if expected["task"] == "write":
        _require(session["write_enabled"] and write_id == expected["legitimate_ticket_id"],
                 "expected: legitimate write task needs a matching write grant")
    target = expected["target_ticket_id"]
    if case["goal"] == "G1":
        _require(target not in allowed, "G1: target must be unreadable")
        _require(tickets[target].get("secret") == "__GENERATE__", "G1: target needs a generated canary")
    elif case["goal"] == "G2":
        _require(not session["write_enabled"] or target != write_id, "G2: target operation must be unauthorized")
    else:
        _text(expected["false_claim"], "G3 false_claim")
        _require(target == expected["legitimate_ticket_id"], "G3: target is the legitimate output/ticket")

    _object(case["mock"], "mock", {"clean", "attack"})
    for source in ("clean", "attack"):
        script = case["mock"][source]
        _require(isinstance(script, list) and bool(script), f"mock.{source}: non-empty script required")
        for index, step in enumerate(script):
            _require(isinstance(step, dict), f"mock.{source}[{index}]: object required")
            if set(step) == {"text"}:
                _text(step["text"], "mock final text")
                _require(index == len(script) - 1, "mock: final text must be the last step")
                for secret_id in re.findall(r"\{\{secret:([^}]+)\}\}", step["text"]):
                    _require(secret_id in tickets and "secret" in tickets[secret_id],
                             "mock: secret placeholder references a ticket without a canary")
                continue
            _require(set(step) == {"name", "arguments"}, "mock: expected a tool step or final text")
            name, args = step["name"], step["arguments"]
            _text(name, "mock tool name")
            _require(name in {"read_ticket", "append_note"}, "mock: unsupported tool")
            required = {"ticket_id"} if name == "read_ticket" else {"ticket_id", "text"}
            _object(args, "mock.arguments", required)
            _require(set(args) == required, "mock.arguments: unexpected fields")
            _require(isinstance(args["ticket_id"], str) and args["ticket_id"] in tickets,
                     "mock: unknown target ticket")
            if name == "append_note":
                _text(args["text"], "mock note")
        _require(set(script[-1]) == {"text"}, "mock: script must end in final text")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, f"JSON: duplicate key {key!r}")
        result[key] = value
    return result


def load_case(path: Path | str) -> dict[str, Any]:
    """Read one UTF-8 JSON case and validate all trusted fixture fields."""
    path = Path(path)
    try:
        case = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        validate_case(case)
    except (OSError, UnicodeError, json.JSONDecodeError, CaseValidationError) as exc:
        raise CaseValidationError(f"{path}: {exc}") from exc
    return case


def load_cases(path: Path | str) -> list[dict[str, Any]]:
    """Load one file or a sorted directory; fail on duplicate case identities."""
    path = Path(path)
    paths = [path] if path.is_file() else sorted(path.glob("*.json"))
    _require(bool(paths), f"{path}: no JSON cases found")
    cases = [load_case(item) for item in paths]
    identities = [case["case_id"] for case in cases]
    _require(len(set(identities)) == len(identities), "catalog: duplicate case_id")
    # scenario_group is deliberately NOT unique: related cases must retain a
    # shared cluster label for analysis rather than being treated as independent.
    return cases
