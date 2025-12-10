"""Utility functions for estimating player placements based on MMR changes."""

from typing import List, Optional
import math
import datetime


# Season tuning constants for early-ladder lobbies
# At the very start of a season, the average lobby MMR is typically lower
# than our long-term cap. We ramp from a lower value up to the full cap
# over the first few weeks.
SEASON_LOBBY_CAP: float = 8500.0
SEASON_MIN_LOBBY_CAP: float = 6800.0
SEASON_RAMP_DAYS: int = 30

SEASON_DEX_THRESHOLD_MAX: float = 8200.0
SEASON_DEX_THRESHOLD_MIN: float = 6800.0


def get_season_lobby_cap(days_since_season_start: Optional[int]) -> float:
    """
    Return an effective lobby MMR cap that ramps up over the season.

    Args:
        days_since_season_start: Days since the start of the season. If None,
            fall back to the default SEASON_LOBBY_CAP.

    Returns:
        A float representing the effective average-lobby cap for this point
        in the season.
    """
    if days_since_season_start is None:
        return SEASON_LOBBY_CAP

    # Clamp to a valid range
    days = max(days_since_season_start, 0)

    if days >= SEASON_RAMP_DAYS:
        return SEASON_LOBBY_CAP

    # Linearly ramp from SEASON_MIN_LOBBY_CAP up to SEASON_LOBBY_CAP
    t = days / SEASON_RAMP_DAYS
    return SEASON_MIN_LOBBY_CAP + t * (SEASON_LOBBY_CAP - SEASON_MIN_LOBBY_CAP)


def get_season_dex_threshold(days_since_season_start: Optional[int]) -> float:
    """
    Return a season-adjusted MMR threshold for when to start applying
    the dex-average lobby adjustment.

    At the beginning of the season, lobbies are generally softer, so we
    start the threshold lower and ramp it up over the first few weeks.

    Args:
        days_since_season_start: Days since the start of the season. If None,
            fall back to the default SEASON_DEX_THRESHOLD_MAX.

    Returns:
        A float representing the effective threshold for this point
        in the season.
    """
    if days_since_season_start is None:
        return SEASON_DEX_THRESHOLD_MAX

    days = max(days_since_season_start, 0)

    if days >= SEASON_RAMP_DAYS:
        return SEASON_DEX_THRESHOLD_MAX

    # Linearly ramp from SEASON_DEX_THRESHOLD_MIN up to SEASON_DEX_THRESHOLD_MAX
    t = days / SEASON_RAMP_DAYS
    return SEASON_DEX_THRESHOLD_MIN + t * (
        SEASON_DEX_THRESHOLD_MAX - SEASON_DEX_THRESHOLD_MIN
    )


def estimate_placement(
    start: float, end: float, days_since_season_start: Optional[int] = None
) -> dict:
    """
    Estimate most likely placement given start and end MMR.

    Args:
        start: Starting MMR value
        end: Ending MMR value
        days_since_season_start: Optional number of days since the start of
            the season. When provided, the "average lobby" cap used in the
            dex_avg calculation is reduced early in the season and ramps
            up to the full value (SEASON_LOBBY_CAP) over time.

    Returns:
        Dictionary with 'placement' (number) and 'delta' (number) keys
    """
    # If no season-day argument was provided, compute it based on a hardcoded season start.
    if days_since_season_start is None:
        season_start = datetime.date(2025, 12, 1)
        today = datetime.date.today()
        days_since_season_start = (today - season_start).days

    gain = end - start

    # Possible placements
    placements = [1, 2, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8]

    # dexAvg (same formula, using starting MMR) but with:
    #  - a season-adjusted lobby cap, and
    #  - a season-adjusted MMR threshold where we start applying the
    #    adjustment. Early in the season, both the lobby cap and the
    #    threshold are lower, then ramp up over the first few weeks.
    lobby_cap = get_season_lobby_cap(days_since_season_start)
    dex_threshold = get_season_dex_threshold(days_since_season_start)

    # As start MMR rises, assume the lobby is closer to the season cap.
    # We dampen the contribution of the player's own MMR using a smooth
    # decay so very high inputs pull much less on the estimated lobby.
    if start <= dex_threshold:
        dex_avg = start
    else:
        # Offset above the threshold, scaled so the effect grows quickly
        # for high MMR inputs.
        offset = start - dex_threshold
        damping = 1 / (1 + (offset / 500) ** 1.3)  # smaller => more pull to cap
        dex_avg = lobby_cap + (start - lobby_cap) * damping

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
