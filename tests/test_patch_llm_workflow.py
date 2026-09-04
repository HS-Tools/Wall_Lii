import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare = load_script("prepare_patch_llm_packet")
process = load_script("process_patch_llm_output")


def baseline_candidates():
    return {
        "source": "hearthstonejson_latest",
        "build_number": "123",
        "source_url": "https://api.hearthstonejson.com/v1/123/enUS/cards.json",
        "raw_card_count": 4,
        "entity_counts": {"current_pool_minions": 3, "current_pool_tavern_spells": 1},
    }, [
        {
            "name": "Ship Jumper",
            "normalized_name": "shipjumper",
            "id": "ROGUE_BG35_700",
            "dbfId": 130701,
            "category": "current_pool_minions",
            "attack": 3,
            "health": 2,
            "techLevel": 4,
            "text": "Deathrattle: Summon a Sky Pirate.",
            "type": "MINION",
        },
        {
            "name": "Back to Back",
            "normalized_name": "backtoback",
            "id": "BG35_Spell_123",
            "dbfId": 131153,
            "category": "current_pool_tavern_spells",
            "cost": 2,
            "text": "Give a minion +4/+4.",
            "type": "BATTLEGROUND_SPELL",
        },
        {
            "name": "Living Azerite",
            "normalized_name": "livingazerite",
            "id": "BG28_707",
            "dbfId": 107939,
            "category": "current_pool_minions",
            "attack": 5,
            "health": 5,
            "techLevel": 4,
            "text": "Whenever you cast a Tavern spell, give Elementals +3/+3.",
            "type": "MINION",
        },
        {
            "name": "Fire-forged Evoker",
            "normalized_name": "fireforgedevoker",
            "id": "BG31_123",
            "dbfId": 120301,
            "category": "current_pool_minions",
            "attack": 3,
            "health": 2,
            "techLevel": 2,
            "text": "Start of Combat: Give your Dragons +1/+1.",
            "type": "MINION",
        },
    ]


def test_prepare_writes_packet_files_and_exact_candidates(tmp_path, monkeypatch):
    def fake_source(*_args):
        return {
            "type": "blog",
            "url": "https://example.test/post",
            "requested_url": "https://example.test/post",
            "title": "Patch Notes",
            "published_at": "2026-04-28T00:00:00Z",
            "created_at": None,
            "updated_at": None,
            "author": "Blizzard Entertainment",
            "raw_html": "<p>Ship Jumper</p><p>Back to Back</p>",
            "plain_text": "Ship Jumper changed. Back to Back changed.",
            "metadata": {},
        }

    monkeypatch.setattr(prepare, "load_source_payload", fake_source)
    monkeypatch.setattr(prepare, "build_baseline_candidates", baseline_candidates)

    args = prepare.parse_args(
        [
            "--url",
            "https://example.test/post",
            "--source-type",
            "blog",
            "--out-dir",
            str(tmp_path),
        ]
    )
    packet = prepare.build_packet(args)
    prepare.write_json(tmp_path / "patch_source.json", packet)
    (tmp_path / "prompt.md").write_text(prepare.prompt_text(), encoding="utf-8")
    prepare.write_json(tmp_path / "llm_output.example.json", {"changes": []})

    source = json.loads((tmp_path / "patch_source.json").read_text())
    candidate_names = {candidate["name"] for candidate in source["candidates"]}

    assert (tmp_path / "prompt.md").exists()
    assert (tmp_path / "llm_output.example.json").exists()
    assert "raw_html" in source["source"]
    assert candidate_names == {"Ship Jumper", "Back to Back"}


def test_process_resolves_valid_output_and_preserves_source_truth():
    baseline, candidates = baseline_candidates()
    source_packet = {"source": {"title": "Patch Notes"}, "baseline": baseline, "candidates": candidates}
    llm_output = {
        "changes": [
            {
                "card_name": "Ship Jumper",
                "change_kind": "modified",
                "changed_fields": {
                    "text": {
                        "old": "Deathrattle: Summon a 1/1 Sky Pirate.",
                        "new": "Rally: Summon a Sky Pirate.",
                    }
                },
                "evidence": "Old: Deathrattle... New: Rally...",
                "confidence": "high",
            }
        ]
    }

    final_output = process.build_final_output(source_packet, llm_output)

    assert final_output["summary"] == {
        "input_change_count": 1,
        "resolved_count": 1,
        "unresolved_count": 0,
    }
    change = final_output["changes"][0]
    assert change["resolved_card_id"] == "ROGUE_BG35_700"
    assert change["baseline_card"]["text"] == "Deathrattle: Summon a Sky Pirate."
    assert change["source_truth_changes"]["text"]["new"] == "Rally: Summon a Sky Pirate."


def test_process_rejects_malformed_output():
    try:
        process.validate_llm_output({"not_changes": []})
    except ValueError as exc:
        assert "changes array" in str(exc)
    else:
        raise AssertionError("Expected malformed output to raise ValueError")


def test_process_preserves_unresolved_names():
    baseline, candidates = baseline_candidates()
    source_packet = {"source": {}, "baseline": baseline, "candidates": candidates}
    llm_output = {
        "changes": [
            {
                "card_name": "Unknown Card",
                "change_kind": "modified",
                "changed_fields": {"attack": {"old": 1, "new": 2}},
                "evidence": "Unknown Card attack is now 2.",
                "confidence": "low",
            }
        ]
    }

    final_output = process.build_final_output(source_packet, llm_output)

    assert final_output["changes"] == []
    assert final_output["unresolved"][0]["card_name"] == "Unknown Card"
    assert final_output["unresolved"][0]["match_status"] == "missing"


def test_candidate_matching_finds_known_blog_and_forum_names():
    _, candidates = baseline_candidates()
    text = """
    Ship Jumper
    Back to Back
    Living Azerite
    Fire-forged Evoker
    """

    matched = prepare.find_mentioned_candidates(text, candidates)
    matched_names = {candidate["name"] for candidate in matched}

    assert matched_names == {
        "Ship Jumper",
        "Back to Back",
        "Living Azerite",
        "Fire-forged Evoker",
    }
