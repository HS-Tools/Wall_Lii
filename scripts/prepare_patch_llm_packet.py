#!/usr/bin/env python3
"""
Prepare a manual LLM handoff packet for Hearthstone Battlegrounds patch notes.

This script does not call an LLM. It fetches the official blog/forum payload,
builds a latest HearthstoneJSON Battlegrounds baseline, finds exact card-name
candidates mentioned in the post text, and writes files you can attach/paste
into ChatGPT.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fetch_blog_post_metadata
import fetch_forum_post_metadata
import ingest_hsbg_entity_diffs


DEFAULT_BLOG_API_URL = fetch_blog_post_metadata.DEFAULT_API_URL
DEFAULT_FORUM_SOURCE_URL = fetch_forum_post_metadata.DEFAULT_SOURCE_URL


def normalize_name(value: str) -> str:
    value = value.lower()
    value = value.replace("’", "'").replace("‘", "'").replace("`", "'")
    return re.sub(r"[^a-z0-9]+", "", value)


def infer_source_type(url: str) -> str:
    if "forums.blizzard.com" in url:
        return "forum"
    if "hearthstone.blizzard.com" in url or "playhearthstone.com" in url:
        return "blog"
    raise ValueError(f"Could not infer source type from URL: {url}")


def load_source_payload(
    url: str,
    source_type: str,
    blog_api_url: str,
    forum_source_url: str,
) -> dict[str, Any]:
    if source_type == "blog":
        payload = fetch_blog_post_metadata.build_payload(url, blog_api_url)
        blog = payload["blog_payload"]
        metadata = payload["metadata"]
        return {
            "type": "blog",
            "url": blog.get("url") or url,
            "requested_url": url,
            "title": blog.get("title"),
            "published_at": blog.get("published_at"),
            "created_at": None,
            "updated_at": None,
            "author": blog.get("author"),
            "raw_html": blog.get("content_html", ""),
            "plain_text": blog.get("plain_text_body", ""),
            "metadata": metadata,
        }

    payload = fetch_forum_post_metadata.build_payload(url, forum_source_url)
    forum = payload["forum_payload"]
    metadata = payload["metadata"]
    return {
        "type": "forum",
        "url": forum.get("url") or url,
        "requested_url": url,
        "title": forum.get("title"),
        "published_at": None,
        "created_at": forum.get("created_at"),
        "updated_at": forum.get("updated_at"),
        "author": forum.get("author"),
        "raw_html": forum.get("cooked_html", ""),
        "plain_text": forum.get("plain_text_body", ""),
        "metadata": metadata,
    }


def build_baseline_candidates() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cards, source_url, build_number = ingest_hsbg_entity_diffs.fetch_cards(
        ingest_hsbg_entity_diffs.CARDS_LATEST_URL
    )
    snapshot = ingest_hsbg_entity_diffs.build_snapshot(build_number, source_url, cards)

    candidates = []
    for row in snapshot.rows:
        card_json = row["card_json"]
        name = card_json.get("name")
        if not name:
            continue
        candidates.append(
            {
                "name": name,
                "normalized_name": normalize_name(str(name)),
                "id": row["card_id"],
                "dbfId": row["dbf_id"],
                "category": row["category"],
                **card_json,
            }
        )

    baseline = {
        "source": "hearthstonejson_latest",
        "build_number": snapshot.build_number,
        "source_url": snapshot.source_url,
        "raw_card_count": snapshot.raw_card_count,
        "entity_counts": snapshot.entity_counts,
    }
    return baseline, candidates


def find_mentioned_candidates(
    plain_text: str, candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    normalized_text = normalize_name(plain_text)
    mentioned = []
    seen = set()

    for candidate in candidates:
        normalized = candidate["normalized_name"]
        if len(normalized) < 3:
            continue
        if normalized in normalized_text:
            key = (candidate["category"], candidate["id"])
            if key in seen:
                continue
            seen.add(key)
            mentioned.append(candidate)

    return sorted(mentioned, key=lambda item: (item["name"].lower(), item["category"]))


def prompt_text() -> str:
    return """You are extracting structured Hearthstone Battlegrounds patch changes.

Use the attached patch_source.json as the only source. Return ONLY valid JSON.

Rules:
- Only include cards/entities explicitly mentioned as changing in the source text.
- Do not infer unrelated HearthstoneJSON changes.
- The source patch text is the source of truth for changed fields.
- Use the candidate cards for IDs and disambiguation, but do not copy baseline values as changed values unless the source text says they changed.
- Preserve exact old/new values from the source text when available.
- If a card name is ambiguous, still use the visible card_name and include the evidence.
- Use confidence: "high", "medium", or "low".

Return this exact top-level shape:

{
  "changes": [
    {
      "card_name": "Ship Jumper",
      "change_kind": "modified",
      "changed_fields": {
        "text": {
          "old": "Deathrattle: ...",
          "new": "Rally: ..."
        }
      },
      "evidence": "Old: Deathrattle... New: Rally...",
      "confidence": "high"
    }
  ]
}

Allowed change_kind values:
- "modified"
- "added"
- "removed"
- "pool_change"
- "bugfix"
- "unknown"

Common changed_fields keys:
- "attack"
- "health"
- "techLevel"
- "cost"
- "armor"
- "text"
- "pool_status"
- "availability"
"""


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_packet(args: argparse.Namespace) -> dict[str, Any]:
    source_type = args.source_type
    if source_type == "auto":
        source_type = infer_source_type(args.url)

    source = load_source_payload(
        args.url,
        source_type,
        args.blog_api_url,
        args.forum_source_url,
    )
    baseline, all_candidates = build_baseline_candidates()
    candidates = find_mentioned_candidates(source["plain_text"], all_candidates)

    return {
        "source": source,
        "baseline": baseline,
        "candidates": candidates,
        "candidate_count": len(candidates),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument(
        "--source-type",
        choices=["blog", "forum", "auto"],
        default="auto",
    )
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--blog-api-url", default=DEFAULT_BLOG_API_URL)
    parser.add_argument("--forum-source-url", default=DEFAULT_FORUM_SOURCE_URL)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    packet = build_packet(args)
    patch_source_path = out_dir / "patch_source.json"
    prompt_path = out_dir / "prompt.md"
    example_path = out_dir / "llm_output.example.json"

    write_json(patch_source_path, packet)
    prompt_path.write_text(prompt_text(), encoding="utf-8")
    write_json(example_path, {"changes": []})

    print(f"wrote: {patch_source_path}")
    print(f"wrote: {prompt_path}")
    print(f"wrote: {example_path}")
    print(f"candidate_count: {packet['candidate_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
