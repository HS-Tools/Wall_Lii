#!/usr/bin/env python3
"""
Script to test different avg_opp thresholds to find the most accurate placement estimations.

This script compares calculated placements against known actual placements to determine
the optimal threshold value.
"""

import sys
from datetime import datetime, timedelta, timezone, date
import pytz
from psycopg2.extras import DictCursor
from dotenv import load_dotenv
from typing import Dict, List, Optional, Tuple
import math

from db_utils import get_db_connection

load_dotenv()

# Configuration - Actual placements data
ACTUAL_PLACEMENTS = {
    "lii": {"date": date(2026, 1, 19), "placements": [4, 4.5, 1, 2, 2, 3, 5]},
    "beterbabbit": {
        "date": date(2026, 1, 21),
        "placements": [5, 1, 1, 1, 1, 2, 1, 1, 2, 1, 4, 7.5, 1, 5, 1],
    },
}

REGION = "NA"  # Region
GAME_MODE = 0  # 0 = solo, 1 = duo

# Thresholds to test
THRESHOLDS_TO_TEST = [8000, 8500, 9000, 9500, 10000, 10500, 11000]

# Table names
LEADERBOARD_SNAPSHOTS = "leaderboard_snapshots"
PLAYERS_TABLE = "players"


def estimate_placement_with_threshold(
    start: float, end: float, threshold: float = 8500
) -> dict:
    """
    Estimate most likely placement given start and end MMR with configurable threshold.

    Args:
        start: Starting MMR value
        end: Ending MMR value
        threshold: Threshold for avg_opp check (default: 8500)

    Returns:
        Dictionary with 'placement' (number) and 'delta' (number) keys
    """
    gain = end - start

    # Possible placements
    placements = [1, 2, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8]

    # Calculate dexAvg - matches PostgreSQL function exactly
    if start < 8200:
        dex_avg = start
    else:
        dex_avg = start - 0.85 * (start - 8500)

    # Find placement with smallest delta
    best_placement = placements[0]
    best_delta = float("inf")

    for p in placements:
        # avgOpp-formula
        avg_opp = start - 148.1181435 * (100 - ((p - 1) * (200.0 / 7.0) + gain))
        if avg_opp > threshold:
            continue

        delta = abs(dex_avg - avg_opp)

        if delta < best_delta:
            best_delta = delta
            best_placement = p

    return {"placement": best_placement, "delta": best_delta}


def get_player_id(cursor, player_name: str) -> Optional[int]:
    """Fetch player_id for a given player_name."""
    cursor.execute(
        f"""
        SELECT player_id, player_name
        FROM {PLAYERS_TABLE}
        WHERE player_name = %s
        """,
        (player_name.lower(),),
    )
    result = cursor.fetchone()
    if result:
        return result["player_id"]
    return None


def get_rating_changes_for_date(
    cursor, player_id: int, region: str, game_mode: int, target_date: date
) -> List[Dict]:
    """
    Query leaderboard_snapshots to get rating changes for a specific date.

    Returns list of dictionaries with snapshot_time, rating, prev_rating
    """
    # Calculate time range (PT timezone)
    pacific = pytz.timezone("America/Los_Angeles")
    # Start of target date in PT
    start_datetime_pt = pacific.localize(
        datetime.combine(target_date, datetime.min.time())
    )
    # End of target date in PT
    end_datetime_pt = pacific.localize(
        datetime.combine(target_date, datetime.max.time())
    )
    # Convert to UTC
    start_datetime_utc = start_datetime_pt.astimezone(timezone.utc)
    end_datetime_utc = end_datetime_pt.astimezone(timezone.utc)

    query = f"""
    WITH all_snapshots AS (
        -- Get all snapshots with previous rating to identify changes
        SELECT 
            ls.player_id,
            ls.game_mode,
            ls.region,
            ls.snapshot_time,
            ls.rating,
            LAG(ls.rating) OVER (
                PARTITION BY ls.player_id, ls.game_mode, ls.region 
                ORDER BY ls.snapshot_time
            ) AS prev_rating
        FROM {LEADERBOARD_SNAPSHOTS} ls
        WHERE ls.player_id = %s
          AND ls.region = %s::region_enum
          AND ls.game_mode = %s::game_mode_enum
          AND ls.snapshot_time >= %s
          AND ls.snapshot_time <= %s
    )
    SELECT 
        player_id,
        game_mode,
        region,
        snapshot_time,
        rating,
        prev_rating
    FROM all_snapshots
    WHERE prev_rating IS NOT NULL 
      AND prev_rating IS DISTINCT FROM rating
    ORDER BY snapshot_time
    """

    cursor.execute(
        query, (player_id, region, str(game_mode), start_datetime_utc, end_datetime_utc)
    )
    return cursor.fetchall()


def calculate_placements_for_threshold(
    rating_changes: List[Dict], threshold: float
) -> List[float]:
    """
    Calculate placements for rating changes using the specified threshold.

    Returns list of placements in order
    """
    placements = []

    for change in rating_changes:
        prev_rating = float(change["prev_rating"])
        rating = float(change["rating"])

        result = estimate_placement_with_threshold(prev_rating, rating, threshold)
        placements.append(result["placement"])

    return placements


def calculate_accuracy_metrics(
    actual: List[float], calculated: List[float]
) -> Dict[str, float]:
    """
    Calculate accuracy metrics comparing actual vs calculated placements.

    Returns dictionary with:
    - exact_matches: number of exact matches
    - match_rate: percentage of exact matches
    - mae: mean absolute error
    - rmse: root mean squared error
    """
    if len(actual) != len(calculated):
        return {
            "exact_matches": 0,
            "match_rate": 0.0,
            "mae": float("inf"),
            "rmse": float("inf"),
            "error": "Length mismatch",
        }

    exact_matches = sum(1 for a, c in zip(actual, calculated) if abs(a - c) < 0.001)
    match_rate = (exact_matches / len(actual)) * 100.0

    errors = [abs(a - c) for a, c in zip(actual, calculated)]
    mae = sum(errors) / len(errors) if errors else 0.0

    squared_errors = [e * e for e in errors]
    rmse = (
        math.sqrt(sum(squared_errors) / len(squared_errors)) if squared_errors else 0.0
    )

    return {
        "exact_matches": exact_matches,
        "match_rate": match_rate,
        "mae": mae,
        "rmse": rmse,
    }


def test_thresholds_for_player(
    cursor, player_name: str, actual_placements: List[float], target_date: date
) -> Dict[int, Dict]:
    """
    Test all thresholds for a player and return results.

    Returns dictionary mapping threshold -> accuracy metrics
    """
    player_id = get_player_id(cursor, player_name)
    if not player_id:
        print(f"Error: Player '{player_name}' not found in database")
        return {}

    # Get rating changes for the target date
    rating_changes = get_rating_changes_for_date(
        cursor, player_id, REGION, GAME_MODE, target_date
    )

    if len(rating_changes) != len(actual_placements):
        print(
            f"Warning: {player_name} has {len(rating_changes)} rating changes but {len(actual_placements)} actual placements"
        )
        print(f"  Rating changes: {len(rating_changes)}")
        print(f"  Actual placements: {len(actual_placements)}")
        if len(rating_changes) == 0:
            return {}

    # Test each threshold
    results = {}
    for threshold in THRESHOLDS_TO_TEST:
        calculated_placements = calculate_placements_for_threshold(
            rating_changes, threshold
        )
        if len(calculated_placements) == len(actual_placements):
            metrics = calculate_accuracy_metrics(
                actual_placements, calculated_placements
            )
            results[threshold] = metrics
            results[threshold]["calculated"] = calculated_placements

    return results


def print_results(
    player_name: str,
    target_date: date,
    actual_placements: List[float],
    results: Dict[int, Dict],
):
    """Print formatted results for a player."""
    print("=" * 100)
    print(
        f"Player: {player_name} | Date: {target_date} | Games: {len(actual_placements)}"
    )
    print("=" * 100)
    print()
    print(f"Actual placements: {[f'{p:.1f}' for p in actual_placements]}")
    print()

    if not results:
        print("No results to display (no rating changes found or length mismatch)")
        print()
        return

    # Print comparison table
    print(
        f"{'Threshold':<12} {'Exact Match':<15} {'Match Rate':<12} {'MAE':<10} {'RMSE':<10} {'Calculated Placements'}"
    )
    print("-" * 100)

    for threshold in sorted(results.keys()):
        metrics = results[threshold]
        if "error" in metrics:
            continue

        calculated_str = ", ".join([f"{p:.1f}" for p in metrics["calculated"]])
        print(
            f"{threshold:<12} "
            f"{metrics['exact_matches']}/{len(actual_placements):<14} "
            f"{metrics['match_rate']:>6.1f}%     "
            f"{metrics['mae']:>6.3f}    "
            f"{metrics['rmse']:>6.3f}    "
            f"[{calculated_str}]"
        )

    print()

    # Find best threshold
    best_threshold = None
    best_match_rate = -1
    best_mae = float("inf")

    for threshold, metrics in results.items():
        if "error" in metrics:
            continue
        if metrics["match_rate"] > best_match_rate:
            best_match_rate = metrics["match_rate"]
            best_threshold = threshold
        elif metrics["match_rate"] == best_match_rate and metrics["mae"] < best_mae:
            best_mae = metrics["mae"]
            best_threshold = threshold

    if best_threshold is not None:
        best_metrics = results[best_threshold]
        print(f"Best threshold: {best_threshold}")
        print(
            f"  Exact matches: {best_metrics['exact_matches']}/{len(actual_placements)} ({best_metrics['match_rate']:.1f}%)"
        )
        print(f"  MAE: {best_metrics['mae']:.3f}")
        print(f"  RMSE: {best_metrics['rmse']:.3f}")
        print()

    print("=" * 100)
    print()


def main():
    """Main entry point."""
    print("=" * 100)
    print("Placement Threshold Accuracy Test")
    print("=" * 100)
    print()
    print(f"Testing thresholds: {THRESHOLDS_TO_TEST}")
    print(f"Region: {REGION} | Game Mode: {'Solo' if GAME_MODE == 0 else 'Duo'}")
    print()

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)

        all_results = {}

        # Test each player
        for player_name, data in ACTUAL_PLACEMENTS.items():
            target_date = data["date"]
            actual_placements = data["placements"]

            print(f"Processing {player_name}...")
            results = test_thresholds_for_player(
                cursor, player_name, actual_placements, target_date
            )
            all_results[player_name] = results

            print_results(player_name, target_date, actual_placements, results)

        # Overall summary
        print("=" * 100)
        print("Overall Summary")
        print("=" * 100)
        print()

        # Aggregate results across all players
        threshold_scores = {}
        for player_name, results in all_results.items():
            for threshold, metrics in results.items():
                if "error" in metrics:
                    continue
                if threshold not in threshold_scores:
                    threshold_scores[threshold] = {
                        "total_matches": 0,
                        "total_games": 0,
                        "total_mae": 0.0,
                        "player_count": 0,
                    }
                threshold_scores[threshold]["total_matches"] += metrics["exact_matches"]
                threshold_scores[threshold]["total_games"] += len(
                    ACTUAL_PLACEMENTS[player_name]["placements"]
                )
                threshold_scores[threshold]["total_mae"] += metrics["mae"]
                threshold_scores[threshold]["player_count"] += 1

        if threshold_scores:
            print(
                f"{'Threshold':<12} {'Total Match Rate':<18} {'Avg MAE':<12} {'Players'}"
            )
            print("-" * 100)

            for threshold in sorted(threshold_scores.keys()):
                scores = threshold_scores[threshold]
                match_rate = (
                    (scores["total_matches"] / scores["total_games"]) * 100.0
                    if scores["total_games"] > 0
                    else 0.0
                )
                avg_mae = (
                    scores["total_mae"] / scores["player_count"]
                    if scores["player_count"] > 0
                    else 0.0
                )
                print(
                    f"{threshold:<12} "
                    f"{scores['total_matches']}/{scores['total_games']} ({match_rate:>5.1f}%)  "
                    f"{avg_mae:>6.3f}      "
                    f"{scores['player_count']}"
                )

            # Find overall best
            best_overall = None
            best_match_rate = -1
            best_avg_mae = float("inf")

            for threshold, scores in threshold_scores.items():
                match_rate = (
                    (scores["total_matches"] / scores["total_games"]) * 100.0
                    if scores["total_games"] > 0
                    else 0.0
                )
                avg_mae = (
                    scores["total_mae"] / scores["player_count"]
                    if scores["player_count"] > 0
                    else 0.0
                )

                if match_rate > best_match_rate:
                    best_match_rate = match_rate
                    best_avg_mae = avg_mae
                    best_overall = threshold
                elif match_rate == best_match_rate and avg_mae < best_avg_mae:
                    best_avg_mae = avg_mae
                    best_overall = threshold

            if best_overall is not None:
                print()
                print(f"Best overall threshold: {best_overall}")
                best_scores = threshold_scores[best_overall]
                match_rate = (
                    best_scores["total_matches"] / best_scores["total_games"]
                ) * 100.0
                avg_mae = best_scores["total_mae"] / best_scores["player_count"]
                print(
                    f"  Total match rate: {best_scores['total_matches']}/{best_scores['total_games']} ({match_rate:.1f}%)"
                )
                print(f"  Average MAE: {avg_mae:.3f}")

        print()
        print("=" * 100)

    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        if conn:
            conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
