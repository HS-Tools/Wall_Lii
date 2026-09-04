# need a way to manage/monitor token usage and make sure I don't error out from not having credits

#!/usr/bin/env python3
"""
Fetch HearthstoneJSON Battlegrounds entities, store normalized snapshots, and
compute structured diffs between adjacent builds.

Examples:
  python scripts/ingest_hsbg_entity_diffs.py --mode historical-dry-run
  python scripts/ingest_hsbg_entity_diffs.py --mode latest-dry-run
  python scripts/ingest_hsbg_entity_diffs.py --mode latest
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


CARDS_LATEST_URL = "https://api.hearthstonejson.com/v1/latest/enUS/cards.json"
LATEST_ENUS_URL = "https://api.hearthstonejson.com/v1/latest/enUS/"
CARDS_BUILD_URL = "https://api.hearthstonejson.com/v1/{build}/enUS/cards.json"
DEFAULT_HISTORICAL_BUILDS = [
    "241135",
    "239550",
    "239422",
    "238087",
    "238003",
    "237510",
    "236529",
    "235290",
    "234747",
    "233275",
]

INTERNAL_CARD_FIELDS = [
    "attack",
    "cost",
    "id",
    "dbfId",
    "race",
    "races",
    "techLevel",
    "mechanics",
    "health",
    "armor",
    "text",
    "type",
    "name",
    "referencedTags",
    "spellSchool",
]

GOLDEN_VERSION_CATEGORIES = {
    "buddies",
    "current_pool_minions",
    "non_current_pool_minions",
    "time_warped_minions",
}

GOLDEN_FILTER_CATEGORIES = GOLDEN_VERSION_CATEGORIES | {
    "trinkets",
    "quest_rewards",
    "current_pool_tavern_spells",
    "non_current_pool_tavern_spells",
}

TEXT_DIFF_PATHS = {("text",), ("golden", "text")}
DEFAULT_TEXT_DIFF_MODEL = "gpt-4o"


@dataclass(frozen=True)
class Snapshot:
    build_number: str
    source_url: str
    raw_card_count: int
    entities: dict[str, list[dict[str, Any]]]
    entity_counts: dict[str, int]
    rows: list[dict[str, Any]]


def load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            os.environ.setdefault(key, value)


def fetch_cards(url: str) -> tuple[list[dict[str, Any]], str, str]:
    request = urllib.request.Request(
        url, headers={"User-Agent": "hsbg-entity-diffs/1.0"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        final_url = response.geturl()
        cards = json.loads(response.read().decode("utf-8"))

    build_number = extract_build_number(final_url, allow_latest=True)
    if build_number == "latest":
        build_number = fetch_latest_build_number()
        final_url = CARDS_BUILD_URL.format(build=build_number)

    return cards, final_url, build_number


def fetch_latest_build_number() -> str:
    request = urllib.request.Request(
        LATEST_ENUS_URL, headers={"User-Agent": "hsbg-entity-diffs/1.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")

    match = re.search(r"/v1/(\d+)/enUS", html)
    if not match:
        raise ValueError("Could not determine latest build number from HearthstoneJSON")

    return match.group(1)


def extract_build_number(url: str, allow_latest: bool = False) -> str:
    match = re.search(r"/v1/([^/]+)/enUS/cards\.json$", url)
    if not match:
        raise ValueError(f"Could not extract build number from URL: {url}")

    build_number = match.group(1)
    if build_number == "latest" and not allow_latest:
        raise ValueError(
            f"Resolved URL still points at latest, not a build number: {url}"
        )

    return build_number


def is_bg(card: dict[str, Any]) -> bool:
    return card.get("set") == "BATTLEGROUNDS"


def card_id(card: dict[str, Any]) -> str:
    return card.get("id") or ""


def is_golden(card: dict[str, Any]) -> bool:
    return card.get("battlegroundsNormalDbfId") is not None or re.search(
        r"_G($|_)", card_id(card)
    )


def is_quest(card: dict[str, Any]) -> bool:
    return is_bg(card) and card.get("type") == "SPELL" and "_Quest_" in card_id(card)


def is_quest_reward(card: dict[str, Any]) -> bool:
    return is_bg(card) and (
        card.get("type") == "BATTLEGROUND_QUEST_REWARD" or "_Reward_" in card_id(card)
    )


def is_trinket(card: dict[str, Any]) -> bool:
    return is_bg(card) and (
        card.get("type") == "BATTLEGROUND_TRINKET"
        or card.get("spellSchool") in {"LESSER_TRINKET", "GREATER_TRINKET"}
    )


def is_time_warped_minion(card: dict[str, Any]) -> bool:
    return (
        is_bg(card)
        and card.get("type") == "MINION"
        and card.get("battlegroundsTimewarpCard") == 1
    )


def is_battlegrounds_minion(card: dict[str, Any]) -> bool:
    return is_bg(card) and card.get("type") == "MINION"


def is_current_battlegrounds_minion(card: dict[str, Any]) -> bool:
    return card.get("isBattlegroundsPoolMinion") is True


def is_battlegrounds_tavern_spell(card: dict[str, Any]) -> bool:
    return (
        is_bg(card)
        and card.get("type") == "BATTLEGROUND_SPELL"
        and card.get("spellSchool") == "TAVERN"
    )


def is_current_battlegrounds_tavern_spell(card: dict[str, Any]) -> bool:
    return (
        is_battlegrounds_tavern_spell(card)
        and card.get("isBattlegroundsPoolSpell") is True
    )


def normalize_card(card: dict[str, Any]) -> dict[str, Any]:
    normalized = {field: card[field] for field in INTERNAL_CARD_FIELDS if field in card}
    if "text" in normalized:
        normalized["text"] = sanitize_card_text(normalized["text"])
    return normalized


def sanitize_card_text(text: Any) -> Any:
    if not isinstance(text, str):
        return text

    text = html.unescape(text)
    text = text.replace("[x]", "")
    text = text.replace("\xa0", " ")
    text = resolve_plural_choice_markers(text)
    text = re.sub(r"</?[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def resolve_plural_choice_markers(text: str) -> str:
    marker_pattern = re.compile(
        r"\|4\s*\(\s*(?P<singular>[^,()]+?)\s*,\s*(?P<plural>[^()]+?)\s*\)"
    )
    chunks = []
    last_index = 0

    for match in marker_pattern.finditer(text):
        singular = match.group("singular").strip()
        plural = match.group("plural").strip()
        prefix = "".join(chunks) + text[last_index : match.start()]
        number_match = None
        for number_match in re.finditer(r"\d+", prefix):
            pass

        chunks.append(text[last_index : match.start()])
        if number_match and int(number_match.group(0)) == 1:
            chunks.append(singular)
        else:
            chunks.append(plural)

        last_index = match.end()

    chunks.append(text[last_index:])
    return "".join(chunks)


def storage_card_json(card: dict[str, Any]) -> dict[str, Any]:
    return strip_keys(
        card,
        {
            "id",
            "dbfId",
            "imageUrl",
            "heroPowerDbfId",
            "battlegroundsPremiumDbfId",
            "battlegroundsNormalDbfId",
            "battlegroundsHero",
            "battlegroundsBuddyDbfId",
            "battlegroundsTimewarpCard",
            "isBattlegroundsPoolMinion",
            "isBattlegroundsPoolSpell",
        },
    )


def with_hero_power(
    hero: dict[str, Any], cards_by_dbf_id: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    normalized = normalize_card(hero)
    hero_power_dbf_id = hero.get("heroPowerDbfId")
    if hero_power_dbf_id is None:
        return normalized

    normalized["heroPowerDbfId"] = hero_power_dbf_id
    hero_power = cards_by_dbf_id.get(hero_power_dbf_id)
    if hero_power:
        normalized["heroPower"] = storage_card_json(normalize_card(hero_power))

    return normalized


def with_golden_version(
    card: dict[str, Any], cards_by_dbf_id: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    normalized = normalize_card(card)
    premium_dbf_id = card.get("battlegroundsPremiumDbfId")
    if premium_dbf_id is None:
        return normalized

    golden_card = cards_by_dbf_id.get(premium_dbf_id)
    if golden_card:
        normalized["golden"] = storage_card_json(normalize_card(golden_card))

    return normalized


def extract_entities(cards: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    cards_by_dbf_id = {
        card["dbfId"]: card for card in cards if card.get("dbfId") is not None
    }

    entities: dict[str, list[dict[str, Any]]] = {
        "heroes": [
            with_hero_power(card, cards_by_dbf_id)
            for card in cards
            if card.get("battlegroundsHero") is True
        ],
        "buddies": [card for card in cards if card.get("isBattlegroundsBuddy") is True],
        "current_pool_minions": [
            card for card in cards if is_current_battlegrounds_minion(card)
        ],
        "non_current_pool_minions": [
            card
            for card in cards
            if is_battlegrounds_minion(card)
            and not is_current_battlegrounds_minion(card)
        ],
        "trinkets": [card for card in cards if is_trinket(card)],
        "quests": [card for card in cards if is_quest(card)],
        "quest_rewards": [card for card in cards if is_quest_reward(card)],
        "current_pool_tavern_spells": [
            card for card in cards if is_current_battlegrounds_tavern_spell(card)
        ],
        "non_current_pool_tavern_spells": [
            card
            for card in cards
            if is_battlegrounds_tavern_spell(card)
            and not is_current_battlegrounds_tavern_spell(card)
        ],
        "spells": [
            card
            for card in cards
            if is_bg(card)
            and card.get("type") == "SPELL"
            and not is_quest(card)
            and not card.get("battlegroundsDarkmoonPrizeTurn")
        ],
        "anomalies": [
            card
            for card in cards
            if is_bg(card) and card.get("type") == "BATTLEGROUND_ANOMALY"
        ],
        "time_warped_minions": [card for card in cards if is_time_warped_minion(card)],
    }

    for category in GOLDEN_FILTER_CATEGORIES:
        entities[category] = [
            card for card in entities[category] if not is_golden(card)
        ]

    for category, found_cards in list(entities.items()):
        if category == "heroes":
            continue

        if category in GOLDEN_VERSION_CATEGORIES:
            entities[category] = [
                with_golden_version(card, cards_by_dbf_id) for card in found_cards
            ]
        else:
            entities[category] = [normalize_card(card) for card in found_cards]

    return entities


def strip_keys(value: Any, keys_to_strip: set[str]) -> Any:
    if isinstance(value, dict):
        return {
            key: strip_keys(child, keys_to_strip)
            for key, child in value.items()
            if key not in keys_to_strip
        }

    if isinstance(value, list):
        return [strip_keys(child, keys_to_strip) for child in value]

    return value


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(card_json: dict[str, Any]) -> str:
    return hashlib.sha256(stable_json(card_json).encode("utf-8")).hexdigest()


def build_snapshot(
    build_number: str, source_url: str, cards: list[dict[str, Any]]
) -> Snapshot:
    entities = extract_entities(cards)
    entity_counts = {
        category: len(found_cards) for category, found_cards in entities.items()
    }
    rows = []

    for category, found_cards in entities.items():
        for card in found_cards:
            cid = card.get("id")
            if not cid:
                continue

            stored_card = storage_card_json(card)
            rows.append(
                {
                    "build_number": build_number,
                    "category": category,
                    "card_id": cid,
                    "dbf_id": card.get("dbfId"),
                    "card_json": stored_card,
                    "content_hash": content_hash(stored_card),
                }
            )

    return Snapshot(
        build_number=build_number,
        source_url=source_url,
        raw_card_count=len(cards),
        entities=entities,
        entity_counts=entity_counts,
        rows=rows,
    )


def row_key(row: dict[str, Any]) -> tuple[str, str]:
    return row["category"], row["card_id"]


def get_by_path(value: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = value
    for segment in path:
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current


def collect_diff_paths(
    old: Any, new: Any, prefix: tuple[str, ...] = ()
) -> set[tuple[str, ...]]:
    if isinstance(old, dict) and isinstance(new, dict):
        paths: set[tuple[str, ...]] = set()
        for key in set(old) | set(new):
            paths |= collect_diff_paths(old.get(key), new.get(key), prefix + (key,))
        return paths

    if old != new:
        return {prefix}

    return set()


def summarize_text_changes(
    text_diff_inputs: list[dict[str, str]],
    model: str = DEFAULT_TEXT_DIFF_MODEL,
) -> dict[str, str]:
    if not text_diff_inputs:
        return {}

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai is required to summarize card text changes") from exc

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required to summarize card text changes")

    prompt = f"""You summarize Hearthstone Battlegrounds card text changes.

INPUT is a JSON array of objects with id, card, path, old, and new.

Return ONLY a JSON object mapping each id to one concise plain-text phrase describing only what changed from old to new.
Do not mention attack, health, cost, tavern tier, armor, or any non-text stat changes.
Do not include explanations, labels, markdown, bullets, or quotes.
Do not copy the full old text or full new text.
Use old-to-new wording with both values when values changed.
Good: Attack bonus reduced from +3 to +2.
Good: Blood Gems increased from 2 to 4.
Bad: Battlecry: Give your other Murlocs +2 Attack.
Bad: Now gives your other Murlocs +2 Attack.

INPUT:
{json.dumps(text_diff_inputs, ensure_ascii=False)}
"""

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You create concise reader-facing summaries of Hearthstone "
                    "Battlegrounds functional card text changes."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    content = (response.choices[0].message.content or "").strip()
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return {}

    if not isinstance(parsed, dict):
        return {}

    summaries = {}
    input_by_id = {item["id"]: item for item in text_diff_inputs}
    for key, value in parsed.items():
        if key in input_by_id and isinstance(value, str) and value.strip():
            summary = value.strip().strip('"')
            if summary in {input_by_id[key]["old"], input_by_id[key]["new"]}:
                summary = fallback_text_diff_summary(
                    input_by_id[key]["old"], input_by_id[key]["new"]
                )
            summaries[key] = summary
    return summaries


def fallback_text_diff_summary(old_text: str, new_text: str) -> str:
    old_numbers = re.findall(r"[+-]?\d+(?:/\d+)?", old_text)
    new_numbers = re.findall(r"[+-]?\d+(?:/\d+)?", new_text)
    if len(old_numbers) == 1 and len(new_numbers) == 1 and old_numbers[0] != new_numbers[0]:
        if "Attack" in old_text and "Attack" in new_text:
            return f"Attack bonus changed from {old_numbers[0]} to {new_numbers[0]}."
        return f"{old_numbers[0]} → {new_numbers[0]}"

    return f"{old_text} → {new_text}"


def field_changes(old_card: dict[str, Any], new_card: dict[str, Any]) -> dict[str, dict[str, Any]]:
    changes = {}

    for path in sorted(collect_diff_paths(old_card, new_card)):
        if not path:
            continue
        path_key = ".".join(path)
        changes[path_key] = {
            "old": get_by_path(old_card, path),
            "new": get_by_path(new_card, path),
        }

    return changes


def collect_text_diff_input(
    diff_index: int,
    card_id: str,
    card_name: str,
    changes: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    inputs = []
    for path in sorted(TEXT_DIFF_PATHS):
        path_key = ".".join(path)
        change = changes.get(path_key)
        if not change:
            continue
        old_text = change.get("old")
        new_text = change.get("new")
        if not isinstance(old_text, str) or not isinstance(new_text, str):
            continue
        inputs.append(
            {
                "id": f"{diff_index}:{path_key}",
                "card_id": card_id,
                "card": card_name,
                "path": path_key,
                "old": old_text,
                "new": new_text,
            }
        )
    return inputs


def apply_text_diff_summaries(
    diffs: list[dict[str, Any]], summaries: dict[str, str]
) -> None:
    for diff_index, diff in enumerate(diffs):
        changes = diff.get("field_changes")
        if not isinstance(changes, dict):
            continue
        for path in TEXT_DIFF_PATHS:
            path_key = ".".join(path)
            summary = summaries.get(f"{diff_index}:{path_key}")
            if summary and path_key in changes:
                changes[path_key]["diff"] = summary


def compute_diffs(
    old_rows: list[dict[str, Any]],
    new_rows: list[dict[str, Any]],
    from_build: str,
    to_build: str,
    text_diff_model: str | None = None,
) -> list[dict[str, Any]]:
    old_by_key = {row_key(row): row for row in old_rows}
    new_by_key = {row_key(row): row for row in new_rows}
    diffs = []
    text_diff_inputs = []

    for key in sorted(set(old_by_key) | set(new_by_key)):
        old_row = old_by_key.get(key)
        new_row = new_by_key.get(key)
        category, cid = key

        if old_row is None and new_row is not None:
            diffs.append(
                {
                    "from_build_number": from_build,
                    "to_build_number": to_build,
                    "category": category,
                    "card_id": cid,
                    "dbf_id": new_row.get("dbf_id"),
                    "change_type": "added",
                    "old_card_json": None,
                    "new_card_json": new_row["card_json"],
                    "field_changes": None,
                }
            )
            continue

        if new_row is None and old_row is not None:
            diffs.append(
                {
                    "from_build_number": from_build,
                    "to_build_number": to_build,
                    "category": category,
                    "card_id": cid,
                    "dbf_id": old_row.get("dbf_id"),
                    "change_type": "removed",
                    "old_card_json": old_row["card_json"],
                    "new_card_json": None,
                    "field_changes": None,
                }
            )
            continue

        if old_row and new_row and old_row["content_hash"] != new_row["content_hash"]:
            changes = field_changes(old_row["card_json"], new_row["card_json"])
            diff_index = len(diffs)
            diffs.append(
                {
                    "from_build_number": from_build,
                    "to_build_number": to_build,
                    "category": category,
                    "card_id": cid,
                    "dbf_id": new_row.get("dbf_id") or old_row.get("dbf_id"),
                    "change_type": "modified",
                    "old_card_json": old_row["card_json"],
                    "new_card_json": new_row["card_json"],
                    "field_changes": changes,
                }
            )
            if text_diff_model:
                card_name = str(
                    new_row["card_json"].get("name")
                    or old_row["card_json"].get("name")
                    or ""
                )
                text_diff_inputs.extend(
                    collect_text_diff_input(diff_index, cid, card_name, changes)
                )

    if text_diff_model and text_diff_inputs:
        summaries = summarize_text_changes(text_diff_inputs, text_diff_model)
        apply_text_diff_summaries(diffs, summaries)

    return diffs


def db_connection():
    import psycopg2

    return psycopg2.connect(
        host=os.environ.get("DB_HOST"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        sslmode="require",
    )


def require_db_env() -> None:
    missing = [
        key
        for key in ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"]
        if not os.environ.get(key)
    ]
    if missing:
        raise RuntimeError(f"Missing required database env vars: {', '.join(missing)}")


def find_previous_build(cur: Any, build_number: str) -> str | None:
    cur.execute(
        """
        select build_number
        from build_snapshots
        where build_number::bigint < %s::bigint
        order by build_number::bigint desc
        limit 1
        """,
        (build_number,),
    )
    previous = cur.fetchone()
    return previous[0] if previous else None


def load_snapshot_rows(cur: Any, build_number: str) -> list[dict[str, Any]]:
    cur.execute(
        """
        select category, card_id, dbf_id, card_json, content_hash
        from card_snapshots
        where build_number = %s
        """,
        (build_number,),
    )
    return [
        {
            "category": row[0],
            "card_id": row[1],
            "dbf_id": row[2],
            "card_json": row[3],
            "content_hash": row[4],
        }
        for row in cur.fetchall()
    ]


def insert_diffs(cur: Any, diffs: list[dict[str, Any]]) -> None:
    if not diffs:
        return

    from psycopg2.extras import Json, execute_values

    execute_values(
        cur,
        """
        insert into card_diffs
          (
            from_build_number,
            to_build_number,
            category,
            card_id,
            dbf_id,
            change_type,
            old_card_json,
            new_card_json,
            field_changes
          )
        values %s
        on conflict (from_build_number, to_build_number, category, card_id)
        do update set
          dbf_id = excluded.dbf_id,
          change_type = excluded.change_type,
          old_card_json = excluded.old_card_json,
          new_card_json = excluded.new_card_json,
          field_changes = excluded.field_changes
        """,
        [
            (
                diff["from_build_number"],
                diff["to_build_number"],
                diff["category"],
                diff["card_id"],
                diff["dbf_id"],
                diff["change_type"],
                Json(diff["old_card_json"]),
                Json(diff["new_card_json"]),
                Json(diff["field_changes"]),
            )
            for diff in diffs
        ],
        page_size=500,
    )


def insert_snapshot(
    snapshot: Snapshot, text_diff_model: str | None = None
) -> tuple[bool, str | None, int]:
    from psycopg2.extras import Json, execute_values

    require_db_env()
    conn = db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select 1 from build_snapshots where build_number = %s",
                    (snapshot.build_number,),
                )
                if cur.fetchone():
                    previous_build = find_previous_build(cur, snapshot.build_number)
                    if not previous_build:
                        return False, None, 0

                    old_rows = load_snapshot_rows(cur, previous_build)
                    new_rows = load_snapshot_rows(cur, snapshot.build_number)
                    diffs = compute_diffs(
                        old_rows,
                        new_rows,
                        previous_build,
                        snapshot.build_number,
                        text_diff_model,
                    )
                    insert_diffs(cur, diffs)
                    return False, previous_build, len(diffs)

                previous_build = find_previous_build(cur, snapshot.build_number)

                old_rows = []
                if previous_build:
                    old_rows = load_snapshot_rows(cur, previous_build)

                diffs = (
                    compute_diffs(
                        old_rows,
                        snapshot.rows,
                        previous_build,
                        snapshot.build_number,
                        text_diff_model,
                    )
                    if previous_build
                    else []
                )

                cur.execute(
                    """
                    insert into build_snapshots
                      (build_number, source_url, raw_card_count, entity_counts)
                    values (%s, %s, %s, %s)
                    """,
                    (
                        snapshot.build_number,
                        snapshot.source_url,
                        snapshot.raw_card_count,
                        Json(snapshot.entity_counts),
                    ),
                )

                execute_values(
                    cur,
                    """
                    insert into card_snapshots
                      (build_number, category, card_id, dbf_id, card_json, content_hash)
                    values %s
                    """,
                    [
                        (
                            row["build_number"],
                            row["category"],
                            row["card_id"],
                            row["dbf_id"],
                            Json(row["card_json"]),
                            row["content_hash"],
                        )
                        for row in snapshot.rows
                    ],
                    page_size=500,
                )

                insert_diffs(cur, diffs)

                return True, previous_build, len(diffs)
    finally:
        conn.close()


def print_snapshot_summary(
    snapshot: Snapshot,
    existed: bool,
    previous_build: str | None = None,
    diffs_inserted: int | None = None,
) -> None:
    print(f"\nbuild_number: {snapshot.build_number}")
    print(f"status: {'already existed' if existed else 'new'}")
    print(f"raw_card_count: {snapshot.raw_card_count}")
    print("entity_counts:")
    for category, count in snapshot.entity_counts.items():
        print(f"  {category}: {count}")
    print(f"previous_build: {previous_build or 'none'}")
    if diffs_inserted is not None:
        print(f"diffs_inserted: {diffs_inserted}")


def fetch_snapshot_for_build(build: str) -> Snapshot:
    cards, source_url, resolved_build = fetch_cards(CARDS_BUILD_URL.format(build=build))
    if resolved_build != build:
        raise ValueError(
            f"Requested build {build}, but HearthstoneJSON resolved {resolved_build}"
        )
    return build_snapshot(resolved_build, source_url, cards)


def run_historical_dry_run(
    builds: list[str], text_diff_model: str | None = None
) -> None:
    snapshots = []
    for build in sorted(set(builds), key=int):
        print(f"Fetching build {build}...")
        snapshots.append(fetch_snapshot_for_build(build))

    previous = None
    for snapshot in snapshots:
        diff_count = None
        previous_build = None
        if previous:
            diffs = compute_diffs(
                previous.rows,
                snapshot.rows,
                previous.build_number,
                snapshot.build_number,
                text_diff_model,
            )
            diff_count = len(diffs)
            previous_build = previous.build_number

        print_snapshot_summary(
            snapshot,
            existed=False,
            previous_build=previous_build,
            diffs_inserted=diff_count,
        )
        previous = snapshot


def run_historical(builds: list[str], text_diff_model: str | None = None) -> None:
    for build in sorted(set(builds), key=int):
        print(f"Fetching build {build}...")
        snapshot = fetch_snapshot_for_build(build)
        inserted, previous_build, diffs_inserted = insert_snapshot(
            snapshot, text_diff_model
        )
        print_snapshot_summary(
            snapshot,
            existed=not inserted,
            previous_build=previous_build,
            diffs_inserted=diffs_inserted,
        )


def run_latest(dry_run: bool, text_diff_model: str | None = None) -> None:
    cards, source_url, build_number = fetch_cards(CARDS_LATEST_URL)
    snapshot = build_snapshot(build_number, source_url, cards)

    if dry_run:
        print_snapshot_summary(snapshot, existed=False, diffs_inserted=0)
        print("\ndry_run: no database reads or writes were performed")
        return

    inserted, previous_build, diffs_inserted = insert_snapshot(
        snapshot, text_diff_model
    )
    print_snapshot_summary(
        snapshot,
        existed=not inserted,
        previous_build=previous_build,
        diffs_inserted=diffs_inserted,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["historical-dry-run", "historical", "latest-dry-run", "latest"],
        default="historical-dry-run",
        help=(
            "historical-dry-run fetches the fixed build set and computes local adjacent diffs; "
            "historical fetches build set and ingests each build into Supabase; "
            "latest-dry-run fetches latest without DB access; latest ingests latest into Supabase"
        ),
    )
    parser.add_argument(
        "--builds",
        nargs="+",
        default=DEFAULT_HISTORICAL_BUILDS,
        help="Build numbers for historical-dry-run mode",
    )
    parser.add_argument(
        "--text-diff-model",
        default=DEFAULT_TEXT_DIFF_MODEL,
        help="OpenAI model to use for concise text diff summaries",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()
    started = datetime.now(timezone.utc)
    print(f"started_at: {started.isoformat()}")

    if args.mode == "historical-dry-run":
        run_historical_dry_run(args.builds, args.text_diff_model)
    elif args.mode == "historical":
        run_historical(args.builds, args.text_diff_model)
    elif args.mode == "latest-dry-run":
        run_latest(dry_run=True, text_diff_model=args.text_diff_model)
    else:
        run_latest(dry_run=False, text_diff_model=args.text_diff_model)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
