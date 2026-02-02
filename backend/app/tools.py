from __future__ import annotations

import json
import os
from typing import Dict, List, Tuple

from .nba import PlayerProfile, fetch_active_players, fetch_player_season_per_game
from .report import generate_csv_report
from .roster import PlayerValue, dollar_value, fantasy_points_per_game, optimize_roster, score_player


def tool_fetch_player_stats() -> Tuple[List[PlayerProfile], Dict[int, Dict[str, float]]]:
    players = fetch_active_players()
    max_players = int(os.getenv("MAX_PLAYER_STATS", "60"))
    if max_players > 0:
        players = players[:max_players]
    stats_by_id: Dict[int, Dict[str, float]] = {}
    for player in players:
        stats_by_id[player.player_id] = fetch_player_season_per_game(player.player_id)
    return players, stats_by_id


def tool_calculate_values(
    players: List[PlayerProfile],
    stats_by_id: Dict[int, Dict[str, float]],
    preferences: List[str],
    budget: float,
) -> List[PlayerValue]:
    valued: List[PlayerValue] = []
    for player in players:
        stats = stats_by_id.get(player.player_id) or {}
        if not stats:
            continue
        fpg = fantasy_points_per_game(stats)
        value = dollar_value(fpg, budget=budget)
        score = score_player(stats, preferences)
        valued.append(
            PlayerValue(
                player_id=player.player_id,
                name=player.full_name,
                team=player.team or "",
                position=player.position or "",
                stats=stats,
                fpg=fpg,
                dollar_value=value,
                score=score,
            )
        )
    return valued


def tool_optimize_roster(
    players: List[PlayerValue],
    budget: float,
    slots: int,
) -> Tuple[List[PlayerValue], float]:
    return optimize_roster(players, budget, slots)


def tool_generate_report(roster: List[PlayerValue]) -> str:
    report_rows = [
        {
            "player_id": player.player_id,
            "name": player.name,
            "team": player.team,
            "position": player.position,
            "fpg": round(player.fpg, 2),
            "dollar_value": round(player.dollar_value, 2),
            "score": round(player.score, 2),
        }
        for player in roster
    ]
    report_name = "team_report"
    if report_rows:
        return generate_csv_report(report_rows, report_name)
    return ""


def serialize_roster(roster: List[PlayerValue]) -> str:
    return json.dumps(
        [
            {
                "player_id": player.player_id,
                "name": player.name,
                "team": player.team,
                "position": player.position,
                "stats": player.stats,
                "fpg": player.fpg,
                "dollar_value": player.dollar_value,
                "score": player.score,
            }
            for player in roster
        ]
    )
