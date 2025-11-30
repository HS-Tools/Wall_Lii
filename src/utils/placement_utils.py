"""Utility functions for estimating player placements based on MMR changes."""

from typing import List
import math


def estimate_placement(start: float, end: float) -> dict:
    """
    Estimate most likely placement given start and end MMR.

    Args:
        start: Starting MMR value
        end: Ending MMR value

    Returns:
        Dictionary with 'placement' (number) and 'delta' (number) keys
    """
    gain = end - start

    # Possible placements
    placements = [1, 2, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8]

    # dexAvg (same formula, using starting MMR)
    dex_avg = start if start < 8200 else (start - 0.85 * (start - 8500))

    # Find placement with smallest delta
    best_placement = placements[0]
    best_delta = float("inf")

    for p in placements:
        # avgOpp-formula
        avg_opp = start - 148.1181435 * (100 - ((p - 1) * (200 / 7) + gain))

        delta = abs(dex_avg - avg_opp)

        if delta < best_delta:
            best_delta = delta
            best_placement = p

    return {"placement": best_placement, "delta": best_delta}


def calculate_placements(ratings: List[float]) -> List[float]:
    """
    Calculate placements for an array of ratings.

    Args:
        ratings: Array of rating values in chronological order

    Returns:
        Array of placements (X ratings returns X-1 placements)
    """
    if len(ratings) < 2:
        return []

    placements = []

    for i in range(len(ratings) - 1):
        start = ratings[i]
        end = ratings[i + 1]
        result = estimate_placement(start, end)
        placements.append(result["placement"])

    return placements


def calculate_average_placement(ratings: List[float]) -> float:
    """
    Calculate the average placement from an array of ratings.

    Args:
        ratings: Array of rating values in chronological order

    Returns:
        Average placement (returns NaN if fewer than 2 ratings)
    """
    placements = calculate_placements(ratings)

    if len(placements) == 0:
        return float("nan")

    return sum(placements) / len(placements)


def calculate_placements_with_average(ratings: List[float], precision: int = 2) -> dict:
    """
    Calculate both placements array and average placement.
    Useful when you need both values without calculating twice.

    Args:
        ratings: Array of rating values in chronological order
        precision: Number of decimal places for average rounding (default: 2)

    Returns:
        Dictionary with 'placements' (list) and 'average' (float) keys
    """
    placements = calculate_placements(ratings)

    if len(placements) == 0:
        average = float("nan")
    else:
        average = sum(placements) / len(placements)

    # Round average if it's a valid number
    if isinstance(average, float) and not math.isnan(average):
        average = round(average, precision)

    return {"placements": placements, "average": average}
