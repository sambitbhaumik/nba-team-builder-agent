from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .db import clear_session_roster, get_session_roster, update_session_roster
from .knowledge import load_preferences
from .nba import PlayerProfile, fetch_active_players, fetch_player_season_per_game
from .report import generate_csv_report
from .roster import PlayerValue, dollar_value, fantasy_points_per_game, optimize_roster, score_player

# Cache file path
CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "player_stats_cache.json"


def _save_player_stats_cache(players: List[PlayerProfile], stats_by_id: Dict[int, Dict[str, float]]) -> None:
    """Save player stats to cache file."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    cache_data = {
        "players": [
            {
                "player_id": p.player_id,
                "full_name": p.full_name,
                "team": p.team,
                "position": p.position,
            }
            for p in players
        ],
        "stats_by_id": stats_by_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(CACHE_FILE, "w") as f:
        json.dump(cache_data, f, indent=2)


def _load_player_stats_cache() -> Optional[Tuple[List[PlayerProfile], Dict[int, Dict[str, float]]]]:
    """Load player stats from cache file. Returns None if cache doesn't exist."""
    if not CACHE_FILE.exists():
        return None
    
    try:
        with open(CACHE_FILE, "r") as f:
            cache_data = json.load(f)
        
        players = [
            PlayerProfile(
                player_id=p["player_id"],
                full_name=p["full_name"],
                team=p.get("team"),
                position=p.get("position"),
            )
            for p in cache_data.get("players", [])
        ]
        stats_by_id = cache_data.get("stats_by_id", {})
        return players, stats_by_id
    except (json.JSONDecodeError, KeyError, FileNotFoundError):
        return None


def tool_fetch_player_stats() -> Tuple[List[PlayerProfile], Dict[int, Dict[str, float]]]:
    """Fetch player stats from NBA API and save to cache."""
    players = fetch_active_players()
    max_players = int(os.getenv("MAX_PLAYER_STATS", "100"))
    if max_players > 0:
        players = players[:max_players]
    stats_by_id: Dict[int, Dict[str, float]] = {}
    for i, player in enumerate(players):
        stats = fetch_player_season_per_game(player.player_id)
        if stats == "error":
            print(f"Error fetching stats for player {player.full_name}")
            continue
        stats_by_id[player.player_id] = stats
        
        # Add delay between requests to avoid rate limiting (skip delay after last player)
        if i < len(players) - 1:
            time.sleep(1.0)  # Wait 1 second between requests
    
    # Save to cache
    _save_player_stats_cache(players, stats_by_id)
    
    return players, stats_by_id


def tool_get_cached_player_stats() -> Tuple[List[PlayerProfile], Dict[int, Dict[str, float]]]:
    """Get player stats from cache. Returns empty lists if cache doesn't exist."""
    cached = _load_player_stats_cache()
    if cached:
        return cached
    return [], {}


def search_roster_players(
    session_id: str,
    budget: float = 200.0,
    count: int = 1,
) -> Dict[str, Any]:
    """
    Search for players suitable for the roster.
    Combines calculation, optimization, and filtering to find the best players.
    Returns a list of player IDs that fit the remaining budget.
    """
    # Get current roster to determine remaining budget
    roster_data = get_current_roster(session_id)
    current_players = roster_data.get("players", [])
    current_player_ids = {p.get("player_id") for p in current_players}
    
    # Calculate remaining budget
    total_cost = sum(p.get("dollar_value", 0.0) for p in current_players)
    remaining_budget = budget - total_cost
    
    # Use the count provided by the LLM agent
    if count <= 0:
        return {
            "success": False,
            "error": "Count must be greater than 0",
            "player_ids": [],
        }
    
    # Fetch cached player stats
    players, stats_by_id = tool_get_cached_player_stats()
    if not players:
        return {
            "success": False,
            "error": "No cached player data available. Please refresh player stats first.",
            "player_ids": [],
        }
    
    # Load user preferences
    preferences = load_preferences()
    
    # Calculate values for all players (excluding those already in roster)
    valued_players: List[PlayerValue] = []
    for player in players:
        # Skip players already in roster
        if player.player_id in current_player_ids:
            continue
        
        stats = stats_by_id.get(str(player.player_id)) or {}
        if not stats:
            continue
        
        fpg = fantasy_points_per_game(stats)
        value = dollar_value(fpg, budget=budget)
        score = score_player(stats, preferences)
        
        valued_players.append(
            PlayerValue(
                player_id=player.player_id,
                name=player.full_name,
                team=player.team or "",
                position=player.position or "",
                stats=stats,
                fpg=fpg,
                dollar_value=value,
                score=score,
                starter=False,
            )
        )
    
    if not valued_players:
        return {
            "success": False,
            "error": "No available players found",
            "player_ids": [],
        }
    
    # Optimize roster to find the best players that fit remaining budget
    optimized_roster, _ = optimize_roster(valued_players, remaining_budget, count)
    
    # Extract player IDs
    player_ids = [p.player_id for p in optimized_roster]
    
    return {
        "success": True,
        "player_ids": player_ids,
        "count": len(player_ids),
    }


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
            "starter": player.starter,
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
                "starter": player.starter,
            }
            for player in roster
        ]
    )


def get_current_roster(session_id: str) -> Dict[str, Any]:
    """Get the current roster state for a session."""
    return get_session_roster(session_id)


def add_player_to_roster(
    session_id: str,
    player_id: int,
    budget: float = 200.0,
    slots: int = 12,
) -> Dict[str, Any]:
    """Add a player to the roster. Returns updated roster state."""
    roster_data = get_session_roster(session_id)
    current_players = roster_data["players"]
    
    # Check if player already exists
    if any(p.get("player_id") == player_id for p in current_players):
        return {"success": False, "error": "Player already in roster", "roster": roster_data}
    
    # Check if roster is full
    if len(current_players) >= slots:
        return {"success": False, "error": "Roster is full", "roster": roster_data}
    
    # Fetch player data from cache
    players, stats_by_id = tool_get_cached_player_stats()
    player_profile = next((p for p in players if p.player_id == player_id), None)
    if not player_profile:
        return {"success": False, "error": "Player not found", "roster": roster_data}
    
    stats = stats_by_id.get(str(player_id)) or {}
    if not stats:
        return {"success": False, "error": "Player stats not available", "roster": roster_data}
    
    # Calculate values
    preferences = load_preferences()
    fpg = fantasy_points_per_game(stats)
    value = dollar_value(fpg, budget=budget)
    score = score_player(stats, preferences)
    
    # Check budget
    total_cost = sum(p.get("dollar_value", 0.0) for p in current_players)
    if total_cost + value > budget:
        return {"success": False, "error": "Exceeds budget", "roster": roster_data}
    
    # Add player
    new_player = {
        "player_id": player_id,
        "name": player_profile.full_name,
        "team": player_profile.team or "",
        "position": player_profile.position or "",
        "fpg": fpg,
        "dollar_value": value,
        "score": score,
        "starter": len(current_players) < 5,
    }
    current_players.append(new_player)
    update_session_roster(session_id, current_players, budget)
    
    return {
        "success": True,
        "message": f"Added {player_profile.full_name} to roster",
        #"roster": get_session_roster(session_id),
    }


def remove_player_from_roster(session_id: str, player_name: str) -> Dict[str, Any]:
    """Remove a player from the roster by name. Returns updated roster state."""
    roster_data = get_session_roster(session_id)
    current_players = roster_data["players"]
    
    # Find and remove player by name (case-insensitive)
    updated_players = [p for p in current_players if p.get("name", "").lower() != player_name.lower()]
    
    if len(updated_players) == len(current_players):
        return {"success": False, "error": f"Player '{player_name}' not in roster", "roster": roster_data}
    
    # Update starter status for remaining players
    for i, p in enumerate(updated_players):
        p["starter"] = i < 5
    
    update_session_roster(session_id, updated_players, roster_data["budget"])
    
    return {
        "success": True,
        "message": f"Removed {player_name} from roster",
    }




def get_player_details(player_name: str, budget: float = 200.0) -> Dict[str, Any]:
    """Get detailed information about a specific player."""
    players, stats_by_id = tool_get_cached_player_stats()
    # Find player by name (case-insensitive)
    player_profile = next((p for p in players if p.full_name.lower() == player_name.lower()), None)
    
    if not player_profile:
        return {"success": False, "error": f"Player '{player_name}' not found"}
    
    player_id = player_profile.player_id
    stats = stats_by_id.get(str(player_id)) or {}
    if not stats:
        return {"success": False, "error": "Player stats not available"}
    
    preferences = load_preferences()
    fpg = fantasy_points_per_game(stats)
    value = dollar_value(fpg, budget=budget)
    score = score_player(stats, preferences)
    
    return {
        "success": True,
        "player_id": player_id,
        "name": player_profile.full_name,
        "team": player_profile.team or "",
        "position": player_profile.position or "",
        "stats": stats,
        "fpg": round(fpg, 2),
        "dollar_value": round(value, 2),
        "score": round(score, 2),
        "starter": False,
    }


# def find_replacements(
#     position: Optional[str] = None,
#     exclude_player_ids: Optional[List[int]] = None,
#     budget: float = 200.0,
#     max_cost: Optional[float] = None,
#     limit: int = 10,
# ) -> List[Dict[str, Any]]:
    """Find replacement players, optionally for a specific position."""
    players, stats_by_id = tool_get_cached_player_stats()
    preferences = load_preferences()
    exclude_ids = set(exclude_player_ids or [])
    
    results = []
    for player in players:
        # Skip excluded players
        if player.player_id in exclude_ids:
            continue
        
        stats = stats_by_id.get(str(player.player_id)) or {}
        if not stats:
            continue
        
        # Apply position filter
        if position and position.lower() != (player.position or "").lower():
            continue
        
        fpg = fantasy_points_per_game(stats)
        value = dollar_value(fpg, budget=budget)
        
        # Apply max_cost filter
        if max_cost and value > max_cost:
            continue
        
        score = score_player(stats, preferences)
        results.append({
            "player_id": player.player_id,
            "name": player.full_name,
            "team": player.team or "",
            "position": player.position or "",
            "fpg": fpg,
            "dollar_value": value,
            "score": score,
            "starter": False,
        })
        
        if len(results) >= limit:
            break
    
    # Sort by score
    results.sort(key=lambda x: x["score"], reverse=True)
    return results
