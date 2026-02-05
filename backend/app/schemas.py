from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentExecuteRequest(BaseModel):
    goal: str
    budget: Optional[float] = None
    session_id: Optional[str] = None
    dry_run: bool = True


class AgentActivity(BaseModel):
    step: str
    status: str
    detail: str


class PlayerStat(BaseModel):
    name: str
    player_id: int
    team: Optional[str] = None
    position: Optional[str] = None
    stats: Dict[str, float]
    fpg: float
    dollar_value: float
    score: float
    starter: bool = False


class RosterResult(BaseModel):
    players: List[PlayerStat]
    total_cost: float
    budget: float


class AgentExecuteResponse(BaseModel):
    session_id: str
    plan: List[str]
    activity_log: List[AgentActivity]
    roster: Optional[RosterResult] = None
    report_path: Optional[str] = None
    knowledge_used: List[str] = Field(default_factory=list)
    message: str


class KnowledgeAddRequest(BaseModel):
    key: str
    value: str
    tags: Optional[str] = None


class KnowledgeQueryResponse(BaseModel):
    items: List[Dict[str, Any]]


class TeamSaveRequest(BaseModel):
    name: str
    roster: Dict[str, Any]
    budget: float
    total_cost: float
    notes: Optional[str] = None
    confirm: bool = False


class TeamListResponse(BaseModel):
    items: List[Dict[str, Any]]


class RosterPlayer(BaseModel):
    player_id: int
    name: str
    team: Optional[str] = None
    position: Optional[str] = None
    fpg: float
    dollar_value: float
    score: float
    starter: bool = False


class CurrentRoster(BaseModel):
    players: List[RosterPlayer] = Field(default_factory=list)
    total_cost: float = 0.0
    budget: float = 200.0


class PlayerSearchRequest(BaseModel):
    name: Optional[str] = None
    position: Optional[str] = None
    team: Optional[str] = None
    min_fpg: Optional[float] = None
    max_cost: Optional[float] = None


class AgentToolResult(BaseModel):
    tool_name: str
    success: bool
    result: Any
    error: Optional[str] = None


class AddPlayerRequest(BaseModel):
    player_id: int
    budget: Optional[float] = 200.0


class OptimizeRosterRequest(BaseModel):
    budget: Optional[float] = None


class PlayerProfileResponse(BaseModel):
    player_id: int
    full_name: str
    team: Optional[str] = None
    position: Optional[str] = None


class FetchPlayerStatsResponse(BaseModel):
    players: List[PlayerProfileResponse]
    stats_by_id: Dict[int, Dict[str, float]]


class CalculateValuesRequest(BaseModel):
    players: Optional[List[PlayerProfileResponse]] = None
    stats_by_id: Optional[Dict[int, Dict[str, float]]] = None
    preferences: List[str]
    budget: float


class PlayerValueResponse(BaseModel):
    player_id: int
    name: str
    team: str
    position: str
    stats: Dict[str, float]
    fpg: float
    dollar_value: float
    score: float
    starter: bool = False


class CalculateValuesResponse(BaseModel):
    valued_players: List[PlayerValueResponse]


class OptimizeRosterFromValuesRequest(BaseModel):
    players: List[PlayerValueResponse]
    budget: float


class OptimizeRosterFromValuesResponse(BaseModel):
    optimized_roster: List[PlayerValueResponse]
    total_cost: float


class GenerateReportRequest(BaseModel):
    roster: List[PlayerValueResponse]


class GenerateReportResponse(BaseModel):
    success: bool
    report_path: Optional[str] = None
