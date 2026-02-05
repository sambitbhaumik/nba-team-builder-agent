from __future__ import annotations

import json
import os
from typing import Any, AsyncGenerator, Dict
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic.type_adapter import R

from .agent import ReActAgent
from .db import append_session_message, init_db, list_teams, query_preferences, save_team
from .knowledge import load_preferences, store_preference
from .roster import PlayerValue
from .schemas import (
    AddPlayerRequest,
    AgentActivity,
    AgentExecuteRequest,
    AgentExecuteResponse,
    # CalculateValuesRequest,
    # CalculateValuesResponse,
    CurrentRoster,
    FetchPlayerStatsResponse,
    GenerateReportRequest,
    GenerateReportResponse,
    KnowledgeAddRequest,
    KnowledgeQueryResponse,
    # OptimizeRosterFromValuesRequest,
    # OptimizeRosterFromValuesResponse,
    OptimizeRosterRequest,
    PlayerProfileResponse,
    # PlayerSearchRequest,
    PlayerStat,
    PlayerValueResponse,
    RosterPlayer,
    RosterResult,
    TeamListResponse,
    TeamSaveRequest,
    UpdateBudgetRequest,
)
from .tools import (
    add_player_to_roster,
    #find_replacements,
    get_current_roster,
    get_player_details,
    remove_player_from_roster,
    search_roster_players,
    tool_fetch_player_stats,
    tool_generate_report,
    tool_get_cached_player_stats,
    update_roster_budget,
)


app = FastAPI(title="NBA Fantasy Team Builder Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/agent/execute", response_model=AgentExecuteResponse)
def agent_execute(request: AgentExecuteRequest) -> AgentExecuteResponse:
    """Execute the ReAct agent with the given goal."""
    # Generate or use provided session_id
    session_id = request.session_id or str(uuid4())
    
    # Create agent instance
    agent = ReActAgent(session_id=session_id)
    
    # Execute agent
    result = agent.execute(
        user_message=request.goal,
        budget=request.budget,
        dry_run=request.dry_run,
    )
    
    # Convert roster to RosterResult format
    roster_result = None
    if result.get("roster") and result["roster"].get("players"):
        players = [
            PlayerStat(
                name=p.get("name", ""),
                player_id=p.get("player_id", 0),
                team=p.get("team"),
                position=p.get("position"),
                stats=p.get("stats", {}),
                fpg=p.get("fpg", 0.0),
                dollar_value=p.get("dollar_value", 0.0),
                score=p.get("score", 0.0),
            )
            for p in result["roster"]["players"]
        ]
        roster_result = RosterResult(
            players=players,
            total_cost=result["roster"].get("total_cost", 0.0),
            budget=result["roster"].get("budget", 200.0),
        )
    
    # Convert activity log to AgentActivity format
    activity_log = [
        AgentActivity(
            step=activity.get("step", ""),
            status=activity.get("status", ""),
            detail=activity.get("detail", ""),
        )
        for activity in result.get("activity_log", [])
    ]
    
    return AgentExecuteResponse(
        session_id=result["session_id"],
        plan=result.get("plan", []),
        activity_log=activity_log,
        roster=roster_result,
        report_path=result.get("report_path"),
        knowledge_used=result.get("knowledge_used", []),
        message=result.get("message", ""),
    )


@app.get("/agent/stream")
async def agent_stream(
    goal: str,
    budget: float | None = None,
    session_id: str | None = None,
) -> StreamingResponse:
    """Stream agent reasoning and actions in real-time."""
    import asyncio
    from collections import deque
    
    # Generate or use provided session_id
    session_id = session_id or str(uuid4())
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        """Generate SSE stream of agent activity."""
        agent = ReActAgent(session_id=session_id)
        
        # Shared list to collect stream events (thread-safe with locks or simple list for now)
        stream_events: deque = deque()
        execution_done = False
        execution_error = None
        
        def stream_callback(event: Dict[str, Any]) -> None:
            """Callback to collect streaming events."""
            stream_events.append(event)
        
        async def execute_agent_async() -> None:
            """Execute agent in async context."""
            nonlocal execution_done, execution_error
            try:
                import concurrent.futures
                loop = asyncio.get_event_loop()
                
                def execute_sync() -> Dict[str, Any]:
                    return agent.execute(
                        user_message=goal,
                        budget=budget,
                        dry_run=False,
                        stream_callback=stream_callback,
                    )
                
                # Run in executor to avoid blocking
                executor = concurrent.futures.ThreadPoolExecutor()
                result = await loop.run_in_executor(executor, execute_sync)
                stream_events.append({"type": "complete", "result": result})
                execution_done = True
            except Exception as e:
                execution_error = str(e)
                stream_events.append({"type": "error", "message": str(e)})
                execution_done = True
        
        try:
            # Start agent execution
            task = asyncio.create_task(execute_agent_async())
            
            # Stream events as they come
            last_event_count = 0
            while not execution_done or len(stream_events) > last_event_count:
                # Check for new events
                while len(stream_events) > last_event_count:
                    event = stream_events[last_event_count]
                    yield f"data: {json.dumps(event)}\n\n"
                    last_event_count += 1
                    
                    if event.get("type") in ["complete", "error"]:
                        break
                
                # Small delay to avoid busy waiting
                await asyncio.sleep(0.1)
            
            # Wait for task to complete
            await task
            
            # Send any remaining events
            while len(stream_events) > last_event_count:
                event = stream_events[last_event_count]
                yield f"data: {json.dumps(event)}\n\n"
                last_event_count += 1
            
            if execution_error:
                yield f"data: {json.dumps({'type': 'error', 'message': execution_error})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )



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


# API endpoints for core tool functions (can be enhanced with LLM agents)
@app.post("/tools/fetch-player-stats", response_model=FetchPlayerStatsResponse)
def api_fetch_player_stats() -> FetchPlayerStatsResponse:
    """
    Fetch player stats from NBA API and save to cache.
    This endpoint refreshes the player pool and their stats.
    """
    players, stats_by_id = tool_fetch_player_stats()
    
    player_profiles = [
        PlayerProfileResponse(
            player_id=p.player_id,
            full_name=p.full_name,
            team=p.team,
            position=p.position,
        )
        for p in players
    ]
    
    return FetchPlayerStatsResponse(
        players=player_profiles,
        stats_by_id=stats_by_id,
    )


@app.post("/tools/get-cached-player-stats", response_model=FetchPlayerStatsResponse)
def api_get_cached_player_stats() -> FetchPlayerStatsResponse:
    """
    Get cached player stats from stored data.
    Returns empty lists if cache doesn't exist.
    """
    players, stats_by_id = tool_get_cached_player_stats()
    
    player_profiles = [
        PlayerProfileResponse(
            player_id=p.player_id,
            full_name=p.full_name,
            team=p.team,
            position=p.position,
        )
        for p in players
    ]
    
    return FetchPlayerStatsResponse(
        players=player_profiles,
        stats_by_id=stats_by_id,
    )


# @app.post("/tools/calculate-values", response_model=CalculateValuesResponse)
# def api_calculate_values(request: CalculateValuesRequest) -> CalculateValuesResponse:
#     """
#     Calculate fantasy values for players based on stats and preferences.
#     Uses cached player stats if players/stats_by_id are not provided.
#     """
#     from .nba import PlayerProfile
#     
#     # Use cached data if players/stats not provided
#     if request.players is None or request.stats_by_id is None:
#         players, stats_by_id = tool_get_cached_player_stats()
#         if not players:
#             raise HTTPException(
#                 status_code=404,
#                 detail="No cached player data available. Please refresh player stats first using /tools/fetch-player-stats"
#             )
#     else:
#         # Convert PlayerProfileResponse back to PlayerProfile
#         players = [
#             PlayerProfile(
#                 player_id=p.player_id,
#                 full_name=p.full_name,
#                 team=p.team,
#                 position=p.position,
#             )
#             for p in request.players
#         ]
#         stats_by_id = request.stats_by_id
#     
#     valued_players = tool_calculate_values(
#         players,
#         stats_by_id,
#         request.preferences,
#         request.budget,
#     )
#     
#     player_values = [
#         PlayerValueResponse(
#             player_id=p.player_id,
#             name=p.name,
#             team=p.team,
#             position=p.position,
#             stats=p.stats,
#             fpg=p.fpg,
#             dollar_value=p.dollar_value,
#             score=p.score,
#         )
#         for p in valued_players
#     ]
#     
#     return CalculateValuesResponse(valued_players=player_values)


# @app.post("/tools/optimize-roster-from-values", response_model=OptimizeRosterFromValuesResponse)
# def api_optimize_roster_from_values(request: OptimizeRosterFromValuesRequest) -> OptimizeRosterFromValuesResponse:
#     """
#     Optimize roster from a list of valued players.
#     This can be enhanced with LLM agent capabilities for intelligent roster optimization.
#     """
#     # Convert PlayerValueResponse back to PlayerValue
#     player_values = [
#         PlayerValue(
#             player_id=p.player_id,
#             name=p.name,
#             team=p.team,
#             position=p.position,
#             stats=p.stats,
#             fpg=p.fpg,
#             dollar_value=p.dollar_value,
#             score=p.score,
#         )
#         for p in request.players
#     ]
#     
#     optimized_roster, total_cost = tool_optimize_roster(
#         player_values,
#         request.budget,
#         request.slots,
#     )
#     
#     optimized_player_values = [
#         PlayerValueResponse(
#             player_id=p.player_id,
#             name=p.name,
#             team=p.team,
#             position=p.position,
#             stats=p.stats,
#             fpg=p.fpg,
#             dollar_value=p.dollar_value,
#             score=p.score,
#         )
#         for p in optimized_roster
#     ]
#     
#     return OptimizeRosterFromValuesResponse(
#         optimized_roster=optimized_player_values,
#         total_cost=total_cost,
#     )


@app.post("/tools/generate-report", response_model=GenerateReportResponse)
def api_generate_report_from_values(request: GenerateReportRequest) -> GenerateReportResponse:
    """Generate a CSV report from a list of player values."""
    # Convert PlayerValueResponse back to PlayerValue
    player_values = [
        PlayerValue(
            player_id=p.player_id,
            name=p.name,
            team=p.team,
            position=p.position,
            stats=p.stats,
            fpg=p.fpg,
            dollar_value=p.dollar_value,
            score=p.score,
        )
        for p in request.roster
    ]
    
    report_path = tool_generate_report(player_values)
    
    return GenerateReportResponse(
        success=True,
        report_path=report_path if report_path else None,
    )


# API endpoints for agent tools
@app.get("/roster/{session_id}", response_model=CurrentRoster)
def api_get_current_roster(session_id: str) -> CurrentRoster:
    """Get the current roster state for a session."""
    roster_data = get_current_roster(session_id)
    players = [
        RosterPlayer(
            player_id=p.get("player_id", 0),
            name=p.get("name", ""),
            team=p.get("team"),
            position=p.get("position"),
            fpg=round(p.get("fpg", 0.0), 2),
            dollar_value=round(p.get("dollar_value", 0.0), 2),
            score=round(p.get("score", 0.0), 2),
            starter=p.get("starter", False),
        )
        for p in roster_data.get("players", [])
    ]
    return CurrentRoster(
        players=players,
        total_cost=round(roster_data.get("total_cost", 0.0), 2),
        budget=roster_data.get("budget", 200.0),
        remaining_budget=round(roster_data.get("remaining_budget", 200.0), 2),
    )


@app.get("/players/search-roster")
def api_search_roster_players(
    session_id: str,
    budget: float = 200.0,
    count: int = 1,
) -> dict[str, Any]:
    """Search for players suitable for the roster. Returns a list of player IDs."""
    return search_roster_players(
        session_id=session_id,
        budget=budget,
        count=count,
    )


# @app.get("/players/search")
# def api_search_players(
#     name: str,
#     budget: float = 200.0,
#     limit: int = 20,
# ) -> list[dict[str, Any]]:
#     """Search for players by name (partial match)."""
#     return search_players(
#         name=name,
#         budget=budget,
#         limit=limit,
#     )


@app.get("/players/{player_name}")
def api_get_player_details(player_name: str, budget: float = 200.0) -> dict[str, Any]:
    """Get detailed information about a specific player."""
    return get_player_details(player_name, budget)


@app.post("/roster/{session_id}/players")
def api_add_player_to_roster(
    session_id: str,
    request: AddPlayerRequest,
) -> dict[str, Any]:
    """Add a player to the roster."""
    return add_player_to_roster(
        session_id,
        request.player_id,
        request.budget or 200.0,
    )


@app.delete("/roster/{session_id}/players/{player_name}")
def api_remove_player_from_roster(
    session_id: str,
    player_name: str,
) -> dict[str, Any]:
    """Remove a player from the roster by name."""
    return remove_player_from_roster(session_id, player_name)


@app.patch("/roster/{session_id}/budget")
def api_update_budget(
    session_id: str,
    request: UpdateBudgetRequest,
) -> dict[str, Any]:
    """Update the budget for the current roster."""
    return update_roster_budget(session_id, request.budget)


# @app.get("/players/replacements")
# def api_find_replacements(
#     position: str | None = None,
#     exclude_player_ids: list[int] | None = None,
#     budget: float = 200.0,
#     max_cost: float | None = None,
#     limit: int = 10,
# ) -> list[dict[str, Any]]:
#     """Find replacement players for a specific position."""
#     return find_replacements(
#         position=position,
#         exclude_player_ids=exclude_player_ids,
#         budget=budget,
#         max_cost=max_cost,
#         limit=limit,
#     )


# @app.post("/roster/{session_id}/optimize")
# def api_optimize_roster(
#     session_id: str,
#     request: OptimizeRosterRequest | None = None,
# ) -> dict[str, Any]:
#     """Optimize the roster using available players via API calls."""
#     import httpx
#     
#     # Get current roster to determine budget/slots if not provided
#     roster_data = get_current_roster(session_id)
#     if request is None:
#         request = OptimizeRosterRequest()
#     budget = request.budget if request.budget is not None else roster_data.get("budget", 200.0)
#     slots = request.slots if request.slots is not None else roster_data.get("slots", 12)
#     
#     preferences = load_preferences()
#     
#     # Call API to calculate values using cached player stats
#     api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
#     with httpx.Client(timeout=60.0) as client:
#         # Calculate values (will use cached player stats automatically)
#         calculate_request = {
#             "preferences": preferences,
#             "budget": budget,
#         }
#         calculate_response = client.post(
#             f"{api_base_url}/tools/calculate-values",
#             json=calculate_request,
#         )
#         calculate_response.raise_for_status()
#         calculate_data = calculate_response.json()
#         
#         # Optimize roster
#         optimize_request = {
#             "players": calculate_data["valued_players"],
#             "budget": budget,
#             "slots": slots,
#         }
#         optimize_response = client.post(
#             f"{api_base_url}/tools/optimize-roster-from-values",
#             json=optimize_request,
#         )
#         optimize_response.raise_for_status()
#         optimize_data = optimize_response.json()
#     
#     # Convert to dict format
#     optimized_players = [
#         {
#             "player_id": p["player_id"],
#             "name": p["name"],
#             "team": p["team"],
#             "position": p["position"],
#             "stats": p["stats"],
#             "fpg": p["fpg"],
#             "dollar_value": p["dollar_value"],
#             "score": p["score"],
#         }
#         for p in optimize_data["optimized_roster"]
#     ]
#     
#     # Update session roster
#     from .db import update_session_roster
#     update_session_roster(session_id, optimized_players, budget, slots)
#     
#     return {
#         "success": True,
#         "roster": get_current_roster(session_id),
#         "total_cost": optimize_data["total_cost"],
#     }


@app.post("/roster/{session_id}/report")
def api_generate_report(session_id: str) -> dict[str, Any]:
    """Generate a CSV report for the current roster via API call."""
    import httpx
    
    roster_data = get_current_roster(session_id)
    players = roster_data.get("players", [])
    
    # Convert to PlayerValueResponse format
    player_values = [
        {
            "player_id": p.get("player_id", 0),
            "name": p.get("name", ""),
            "team": p.get("team", ""),
            "position": p.get("position", ""),
            "stats": p.get("stats", {}),
            "fpg": p.get("fpg", 0.0),
            "dollar_value": p.get("dollar_value", 0.0),
            "score": p.get("score", 0.0),
        }
        for p in players
    ]
    
    # Call API to generate report
    api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    with httpx.Client(timeout=30.0) as client:
        report_request = {"roster": player_values}
        report_response = client.post(
            f"{api_base_url}/tools/generate-report",
            json=report_request,
        )
        report_response.raise_for_status()
        report_data = report_response.json()
    
    return {
        "success": report_data.get("success", True),
        "report_path": report_data.get("report_path"),
    }
