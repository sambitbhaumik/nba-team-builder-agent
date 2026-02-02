from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from nba_api.stats.endpoints import commonallplayers, playercareerstats

# Cache for active players: (data, timestamp)
_active_players_cache: Tuple[Optional[List["PlayerProfile"]], float] = (None, 0.0)
_CACHE_TTL_SECONDS: float = 3600.0  # 1 hour


@dataclass
class PlayerProfile:
    player_id: int
    full_name: str
    team: Optional[str]
    position: Optional[str]


def fetch_active_players(force_refresh: bool = False) -> List[PlayerProfile]:
    """Fetch active players with caching. Cache TTL is 1 hour."""
    global _active_players_cache
    
    cached_data, cached_time = _active_players_cache
    now = time.time()
    
    if not force_refresh and cached_data is not None and (now - cached_time) < _CACHE_TTL_SECONDS:
        return cached_data
    
    data = commonallplayers.CommonAllPlayers(is_only_current_season=1).get_data_frames()[0]
    players: List[PlayerProfile] = []
    for _, row in data.iterrows():
        if row.get("ROSTERSTATUS") != 1:
            continue
        players.append(
            PlayerProfile(
                player_id=int(row["PERSON_ID"]),
                full_name=str(row["DISPLAY_FIRST_LAST"]),
                team=str(row.get("TEAM_NAME") or ""),
                position=None,
            )
        )
    
    _active_players_cache = (players, now)
    return players


def fetch_player_season_per_game(player_id: int) -> Dict[str, float]:
    data = playercareerstats.PlayerCareerStats(player_id=player_id).get_data_frames()
    if not data:
        return {}
    # The first DataFrame in the list (SeasonTotalsRegularSeason) contains the year-by-year regular season stats.
    season_totals = data[0]
    if season_totals.empty:
        return {}

    # fetching the recent season stats
    last = season_totals.iloc[-1]
    games = float(last.get("GP") or 0)
    if games <= 0:
        return {}
    
    per_game = {
        "pts": float(last.get("PTS") or 0) / games,
        "reb": float(last.get("REB") or 0) / games,
        "oreb": float(last.get("OREB") or 0) / games,
        "dreb": float(last.get("DREB") or 0) / games,
        "ast": float(last.get("AST") or 0) / games,
        "stl": float(last.get("STL") or 0) / games,
        "blk": float(last.get("BLK") or 0) / games,
        "tov": float(last.get("TOV") or 0) / games,
        "fg3m": float(last.get("FG3M") or 0) / games,
        "fg_pct": float(last.get("FG_PCT") or 0),
        "fg3_pct": float(last.get("FG3_PCT") or 0),
        "ft_pct": float(last.get("FT_PCT") or 0),
        "age": last.get("PLAYER_AGE") or 0,
    }
    return per_game
