#!/usr/bin/env python3
"""
Validate and enrich manually pasted LLM patch extraction output.

This script does not call an LLM. It consumes patch_source.json from
prepare_patch_llm_packet.py plus a JSON response pasted from ChatGPT.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def normalize_name(value: str) -> str:
    value = value.lower()
    value = value.replace("’", "'").replace("‘", "'").replace("`", "'")
    return re.sub(r"[^a-z0-9]+", "", value)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def validate_llm_output(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        raise ValueError("LLM output must be a JSON object")

    changes = value.get("changes")
    if not isinstance(changes, list):
        raise ValueError("LLM output must contain a changes array")

    validated = []
    for index, change in enumerate(changes):
        if not isinstance(change, dict):
            raise ValueError(f"changes[{index}] must be an object")
        card_name = change.get("card_name")
        if not isinstance(card_name, str) or not card_name.strip():
            raise ValueError(f"changes[{index}].card_name must be a non-empty string")
        changed_fields = change.get("changed_fields", {})
        if not isinstance(changed_fields, dict):
            raise ValueError(f"changes[{index}].changed_fields must be an object")

        validated.append(
            {
                "card_name": card_name.strip(),
                "change_kind": change.get("change_kind", "unknown"),
                "changed_fields": changed_fields,
                "evidence": change.get("evidence", ""),
                "confidence": change.get("confidence", "unknown"),
                "raw_change": change,
            }
        )

    return validated


def candidates_by_normalized_name(
    candidates: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    by_name: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        name = candidate.get("name")
        if not isinstance(name, str) or not name:
            continue
        normalized = candidate.get("normalized_name") or normalize_name(name)
        by_name.setdefault(normalized, []).append(candidate)
    return by_name


def baseline_card(candidate: dict[str, Any]) -> dict[str, Any]:
    omitted = {"normalized_name", "category"}
    return {key: value for key, value in candidate.items() if key not in omitted}


def resolve_changes(
    changes: list[dict[str, Any]], candidates: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_name = candidates_by_normalized_name(candidates)
    resolved = []
    unresolved = []

    for change in changes:
        normalized = normalize_name(change["card_name"])
        matches = by_name.get(normalized, [])

        if len(matches) != 1:
            unresolved.append(
                {
                    "card_name": change["card_name"],
                    "match_status": "missing" if not matches else "ambiguous",
                    "match_count": len(matches),
                    "candidate_matches": [
                        {
                            "name": item.get("name"),
                            "id": item.get("id"),
                            "dbfId": item.get("dbfId"),
                            "category": item.get("category"),
                        }
                        for item in matches
                    ],
                    "source_truth_changes": change["changed_fields"],
                    "evidence": change["evidence"],
                    "confidence": change["confidence"],
                    "raw_change": change["raw_change"],
                }
            )
            continue

        candidate = matches[0]
        resolved.append(
            {
                "card_name": change["card_name"],
                "resolved_card_id": candidate.get("id"),
                "dbf_id": candidate.get("dbfId"),
                "category": candidate.get("category"),
                "match_status": "resolved",
                "match_confidence": "high",
                "change_kind": change["change_kind"],
                "baseline_card": baseline_card(candidate),
                "source_truth_changes": change["changed_fields"],
                "evidence": change["evidence"],
                "extraction_confidence": change["confidence"],
                "raw_change": change["raw_change"],
            }
        )

    return resolved, unresolved


def build_final_output(source_packet: dict[str, Any], llm_output: Any) -> dict[str, Any]:
    candidates = source_packet.get("candidates", [])
    if not isinstance(candidates, list):
        raise ValueError("source-file must contain a candidates array")

    changes = validate_llm_output(llm_output)
    resolved, unresolved = resolve_changes(changes, candidates)

    return {
        "source": source_packet.get("source"),
        "baseline": source_packet.get("baseline"),
        "changes": resolved,
        "unresolved": unresolved,
        "summary": {
            "input_change_count": len(changes),
            "resolved_count": len(resolved),
            "unresolved_count": len(unresolved),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-file", required=True)
    parser.add_argument("--llm-output", required=True)
    parser.add_argument("--out-file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_packet = load_json(Path(args.source_file))
    llm_output = load_json(Path(args.llm_output))
    final_output = build_final_output(source_packet, llm_output)
    rendered = json.dumps(final_output, indent=2, ensure_ascii=False) + "\n"

    if args.out_file:
        Path(args.out_file).write_text(rendered, encoding="utf-8")
        print(f"wrote: {args.out_file}")
        print(json.dumps(final_output["summary"], indent=2))
    else:
        sys.stdout.write(rendered)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
