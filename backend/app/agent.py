from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional
from uuid import uuid4

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from .db import append_session_message, save_team
from .knowledge import load_preferences
from .schemas import AgentActivity, PlayerStat, RosterResult
from .tools import (
    serialize_roster,
    tool_calculate_values,
    tool_fetch_player_stats,
    tool_generate_report,
    tool_optimize_roster,
)


@dataclass
class AgentResult:
    plan: List[str]
    activity_log: List[AgentActivity]
    roster: Optional[RosterResult]
    report_path: Optional[str]
    knowledge_used: List[str]
    message: str


class StreamManager:
    def __init__(self) -> None:
        self._queues: Dict[str, asyncio.Queue[str]] = {}

    def get_queue(self, session_id: str) -> asyncio.Queue[str]:
        if session_id not in self._queues:
            self._queues[session_id] = asyncio.Queue()
        return self._queues[session_id]

    async def publish(self, session_id: str, payload: Dict[str, str]) -> None:
        queue = self.get_queue(session_id)
        await queue.put(json.dumps(payload))

    async def subscribe(self, session_id: str):
        queue = self.get_queue(session_id)
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=25)
                yield f"data: {message}\n\n"
            except asyncio.TimeoutError:
                yield "data: {}\n\n"


stream_manager = StreamManager()


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(model="gpt-4o-mini", temperature=0)


async def _llm_plan(goal: str) -> List[str]:
    llm = _get_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a concise NBA fantasy roster planner."),
            ("user", "Create a short plan (5-7 steps) for this goal: {goal}"),
        ]
    )
    chain = prompt | llm
    response = chain.invoke({"goal": goal})
    content = getattr(response, "content", "") or ""
    steps = [line.strip("- ").strip() for line in content.splitlines() if line.strip()]
    if not steps:
        raise RuntimeError("LLM returned an empty plan")
    return steps[:7]


def _parse_budget(goal: str, fallback: float = 150.0) -> float:
    match = re.search(r"\$?\s*(\d{2,4})", goal)
    if match:
        return float(match.group(1))
    return fallback


def _parse_preferences(goal: str) -> List[str]:
    prefs = []
    lowered = goal.lower()
    if "3-point" in lowered or "3 point" in lowered or "3pt" in lowered:
        prefs.append("3pt")
    if "defense" in lowered or "defensive" in lowered or "steal" in lowered or "block" in lowered:
        prefs.append("defense")
    return prefs


class AgentRunner:
    def __init__(self, slots: int = 12) -> None:
        self.slots = slots

    async def execute(
        self,
        goal: str,
        budget: Optional[float],
        session_id: str,
        dry_run: bool,
    ) -> AgentResult:
        activity_log: List[AgentActivity] = []
        knowledge_used: List[str] = []
        plan = await _llm_plan(goal)

        parsed_budget = budget or _parse_budget(goal)
        preferences = _parse_preferences(goal)
        stored_preferences = load_preferences()
        if stored_preferences:
            knowledge_used.extend(stored_preferences[:3])
            preferences.extend([pref for pref in stored_preferences if pref in ("3pt", "defense")])

        activity_log.append(
            AgentActivity(
                step="Parse goal",
                status="ok",
                detail=f"Budget ${parsed_budget:.0f}, preferences {preferences or ['none']}",
            )
        )
        await stream_manager.publish(
            session_id,
            {"step": "Parse goal", "status": "ok", "detail": activity_log[-1].detail},
        )

        max_players = int(os.getenv("MAX_PLAYER_STATS", "60"))
        detail = f"Calling NBA API (limit {max_players})" if max_players > 0 else "Calling NBA API"
        activity_log.append(AgentActivity(step="Fetch stats", status="running", detail=detail))
        await stream_manager.publish(
            session_id,
            {"step": "Fetch stats", "status": "running", "detail": detail},
        )
        try:
            players, stats_by_id = tool_fetch_player_stats()
            detail = f"Fetched {len(players)} players"
            status = "ok"
        except Exception as exc:
            players, stats_by_id = [], {}
            detail = f"NBA API failed: {exc}"
            status = "error"
        activity_log.append(AgentActivity(step="Fetch stats", status=status, detail=detail))
        await stream_manager.publish(
            session_id,
            {"step": "Fetch stats", "status": status, "detail": detail},
        )

        activity_log.append(
            AgentActivity(step="Calculate values", status="running", detail="Computing FPG and $ values")
        )
        await stream_manager.publish(
            session_id,
            {"step": "Calculate values", "status": "running", "detail": "Computing FPG and $ values"},
        )
        valued_players = tool_calculate_values(players, stats_by_id, preferences, budget=parsed_budget)
        activity_log.append(
            AgentActivity(step="Calculate values", status="ok", detail=f"Scored {len(valued_players)} players")
        )
        await stream_manager.publish(
            session_id,
            {"step": "Calculate values", "status": "ok", "detail": f"Scored {len(valued_players)} players"},
        )
        if not valued_players:
            message = "No player stats available yet. Try again later."
            append_session_message(session_id, "assistant", message)
            return AgentResult(
                plan=plan,
                activity_log=activity_log,
                roster=None,
                report_path=None,
                knowledge_used=knowledge_used,
                message=message,
            )

        activity_log.append(
            AgentActivity(step="Optimize roster", status="running", detail="Selecting best roster")
        )
        await stream_manager.publish(
            session_id,
            {"step": "Optimize roster", "status": "running", "detail": "Selecting best roster"},
        )
        roster, total_cost = tool_optimize_roster(valued_players, parsed_budget, self.slots)
        activity_log.append(
            AgentActivity(
                step="Optimize roster",
                status="ok",
                detail=f"Selected {len(roster)} players for ${total_cost:.2f}",
            )
        )
        await stream_manager.publish(
            session_id,
            {
                "step": "Optimize roster",
                "status": "ok",
                "detail": f"Selected {len(roster)} players for ${total_cost:.2f}",
            },
        )

        report_path = tool_generate_report(roster) if roster else None
        if report_path:
            activity_log.append(
                AgentActivity(step="Generate report", status="ok", detail=f"Saved CSV at {report_path}")
            )
            await stream_manager.publish(
                session_id,
                {"step": "Generate report", "status": "ok", "detail": f"Saved CSV at {report_path}"},
            )

        roster_result = RosterResult(
            players=[
                PlayerStat(
                    name=player.name,
                    player_id=player.player_id,
                    team=player.team,
                    position=player.position,
                    stats=player.stats,
                    fpg=player.fpg,
                    dollar_value=player.dollar_value,
                    score=player.score,
                )
                for player in roster
            ],
            total_cost=total_cost,
            budget=parsed_budget,
        )

        message = (
            "Roster ready. Review the team and approve to save."
            if dry_run
            else "Roster saved to history."
        )

        if not dry_run and roster:
            team_id = str(uuid4())
            save_team(
                team_id=team_id,
                name="Auto-built roster",
                roster_json=serialize_roster(roster),
                budget=parsed_budget,
                total_cost=total_cost,
                notes="Saved by agent",
            )

        append_session_message(session_id, "assistant", message)

        return AgentResult(
            plan=plan,
            activity_log=activity_log,
            roster=roster_result,
            report_path=report_path,
            knowledge_used=knowledge_used,
            message=message,
        )
