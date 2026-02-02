from __future__ import annotations

import json
from typing import AsyncGenerator
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .agent import AgentRunner, stream_manager
from .db import append_session_message, init_db, list_teams, query_preferences, save_team
from .knowledge import store_preference
from .schemas import (
    AgentExecuteRequest,
    AgentExecuteResponse,
    KnowledgeAddRequest,
    KnowledgeQueryResponse,
    TeamListResponse,
    TeamSaveRequest,
)


app = FastAPI(title="NBA Fantasy Team Builder Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent_runner = AgentRunner()


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/agent/execute", response_model=AgentExecuteResponse)
async def agent_execute(payload: AgentExecuteRequest) -> AgentExecuteResponse:
    session_id = payload.session_id or str(uuid4())
    append_session_message(session_id, "user", payload.goal)
    result = await agent_runner.execute(
        goal=payload.goal,
        budget=payload.budget,
        session_id=session_id,
        dry_run=payload.dry_run,
    )
    return AgentExecuteResponse(
        session_id=session_id,
        plan=result.plan,
        activity_log=result.activity_log,
        roster=result.roster,
        report_path=result.report_path,
        knowledge_used=result.knowledge_used,
        message=result.message,
    )


@app.get("/agent/stream")
async def agent_stream(session_id: str) -> StreamingResponse:
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    async def event_generator() -> AsyncGenerator[str, None]:
        async for message in stream_manager.subscribe(session_id):
            yield message

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/knowledge/add")
def knowledge_add(payload: KnowledgeAddRequest) -> dict:
    store_preference(payload.key, payload.value, payload.tags)
    return {"status": "saved"}


@app.get("/knowledge/query", response_model=KnowledgeQueryResponse)
def knowledge_query() -> KnowledgeQueryResponse:
    items = query_preferences()
    return KnowledgeQueryResponse(items=items)


@app.post("/teams/save")
def teams_save(payload: TeamSaveRequest) -> dict:
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="confirm=true required to save team")
    team_id = str(uuid4())
    save_team(
        team_id=team_id,
        name=payload.name,
        roster_json=json.dumps(payload.roster),
        budget=payload.budget,
        total_cost=payload.total_cost,
        notes=payload.notes,
    )
    return {"status": "saved", "team_id": team_id}


@app.get("/teams", response_model=TeamListResponse)
def teams_list() -> TeamListResponse:
    return TeamListResponse(items=list_teams())
