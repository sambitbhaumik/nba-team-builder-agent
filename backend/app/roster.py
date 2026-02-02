from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class PlayerValue:
    player_id: int
    name: str
    team: str
    position: str
    stats: Dict[str, float]
    fpg: float
    dollar_value: float
    score: float


def fantasy_points_per_game(stats: Dict[str, float]) -> float:
    """Calculate fantasy points per game using standard scoring with efficiency bonuses."""
    base_score = (
        stats.get("pts", 0) * 1
        + stats.get("reb", 0) * 1.2
        + stats.get("ast", 0) * 1.5
        + stats.get("stl", 0) * 2
        + stats.get("blk", 0) * 2
        + stats.get("tov", 0) * -1
    )
    
    # Efficiency bonuses based on shooting percentages
    fg_pct = stats.get("fg_pct", 0)
    fg3_pct = stats.get("fg3_pct", 0)
    ft_pct = stats.get("ft_pct", 0)
    
    # Bonus for high efficiency (above league average thresholds)
    efficiency_bonus = 0.0
    if fg_pct > 0.45:
        efficiency_bonus += (fg_pct - 0.45) * 10  # Reward FG% above 45%
    if fg3_pct > 0.35:
        efficiency_bonus += (fg3_pct - 0.35) * 8  # Reward 3PT% above 35%
    if ft_pct > 0.75:
        efficiency_bonus += (ft_pct - 0.75) * 5  # Reward FT% above 75%
    
    return base_score + efficiency_bonus


def dollar_value(fpg: float, avg_fpg: float = 25.0, budget: float = 200.0, slots: int = 12) -> float:
    return (fpg / avg_fpg) * (budget / slots)


def score_player(stats: Dict[str, float], preferences: List[str]) -> float:
    """Score a player based on fantasy points, user preferences, and age."""
    score = fantasy_points_per_game(stats)
    
    # Age factor from stats: prime years (25-29) get bonus, younger players get slight bonus for upside
    # older players (30+) get slight penalty for potential decline
    age = int(stats.get("age", 0))
    if age > 0:
        if 25 <= age <= 29:
            score *= 1.05  # Prime years bonus
        elif 22 <= age < 25:
            score *= 1.02  # Young upside bonus
        elif age >= 33:
            score *= 0.95  # Decline risk penalty
        elif age >= 30:
            score *= 0.98  # Slight decline risk
    
    if "3pt" in preferences:
        score += stats.get("fg3m", 0) * 1.5
        # Bonus for 3PT shooting efficiency
        fg3_pct = stats.get("fg3_pct", 0)
        if fg3_pct > 0.38:
            score += (fg3_pct - 0.38) * 15
    
    if "defense" in preferences:
        score += stats.get("stl", 0) * 1.8 + stats.get("blk", 0) * 1.8
        # Defensive rebounds contribute to defense
        score += stats.get("dreb", 0) * 0.5
    
    if "rebounding" in preferences:
        score += stats.get("oreb", 0) * 2.0 + stats.get("dreb", 0) * 1.0
    
    if "efficiency" in preferences:
        fg_pct = stats.get("fg_pct", 0)
        ft_pct = stats.get("ft_pct", 0)
        if fg_pct > 0.50:
            score += (fg_pct - 0.50) * 20
        if ft_pct > 0.80:
            score += (ft_pct - 0.80) * 10
    
    if "youth" in preferences and age > 0:
        # Strong preference for younger players
        if age < 25:
            score *= 1.15
        elif age < 28:
            score *= 1.05
    
    if "veteran" in preferences and age > 0:
        # Preference for experienced players
        if age >= 30:
            score *= 1.10
        elif age >= 28:
            score *= 1.05
    
    return score


def optimize_roster(
    players: List[PlayerValue],
    budget: float,
    slots: int,
) -> Tuple[List[PlayerValue], float]:
    if not players:
        return [], 0.0
    sorted_players = sorted(players, key=lambda p: (p.score / max(p.dollar_value, 0.1)), reverse=True)
    roster: List[PlayerValue] = []
    total_cost = 0.0
    for player in sorted_players:
        if len(roster) >= slots:
            break
        if total_cost + player.dollar_value <= budget:
            roster.append(player)
            total_cost += player.dollar_value
    if len(roster) < slots:
        remaining = [p for p in players if p not in roster]
        remaining.sort(key=lambda p: p.dollar_value)
        for player in remaining:
            if len(roster) >= slots:
                break
            if total_cost + player.dollar_value <= budget:
                roster.append(player)
                total_cost += player.dollar_value
    return roster, total_cost
