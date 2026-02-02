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
