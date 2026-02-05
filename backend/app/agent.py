from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from .db import (
    append_session_message,
    get_session_messages,
    get_session_roster,
    save_session_messages,
    update_session_roster,
)
from .knowledge import load_preferences

# Configure logging
class ColorFormatter(logging.Formatter):
    """Custom formatter to add colors to log levels."""
    
    GREY = "\x1b[38;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    BLUE = "\x1b[34;20m"
    RESET = "\x1b[0m"
    FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    FORMATS = {
        logging.DEBUG: GREY + FORMAT + RESET,
        logging.INFO: BLUE + FORMAT + RESET,
        logging.WARNING: YELLOW + FORMAT + RESET,
        logging.ERROR: RED + FORMAT + RESET,
        logging.CRITICAL: BOLD_RED + FORMAT + RESET
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

# Setup logger
logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)

# Create console handler with color formatter
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(ColorFormatter())
    logger.addHandler(ch)

# Load .env file from the backend directory (parent of app directory)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Initialize OpenAI client for OpenRouter
api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    raise ValueError(
        "OPENROUTER_API_KEY environment variable is not set. "
        "Please ensure the .env file exists in the backend directory."
    )

client = OpenAI(
    api_key=api_key,
    base_url="https://openrouter.ai/api/v1",
)

# API base URL for tool endpoints
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Tool definitions for OpenAI function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_roster",
            "description": "Get the current roster state including players currently in the roster, budget allotted for the roster, and total cost already spent.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_roster_players",
            "description": "Search for players suitable for the roster. This tool calculates values, optimizes selection, and returns a list of player IDs that fit the remaining budget. Use this when you need to find players to fill roster slots.",
            "parameters": {
                "type": "object",
                "properties": {
                    # "session_id": {
                    #     "type": "string",
                    #     "description": "The session ID",
                    # },
                    "search_budget": {
                        "type": "number",
                        "description": "Total budget allotted for the search (float). May be less than the total budget of the roster if some slots are already filled. (default 200.0)",
                    },
                    "budget": {
                        "type": "number",
                        "description": "Total budget allotted for the roster (float). Used for calculating budget-adjusted dollar value of the player (default 200.0)",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of players to find (default 1).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_player_details",
            "description": "Get detailed information about a specific player including stats, FPG, dollar value, and score.",
            "parameters": {
                "type": "object",
                "properties": {
                    "player_name": {
                        "type": "string",
                        "description": "The full name of the player to get details for",
                    },
                    "budget": {
                        "type": "number",
                        "description": "Total budget allotted for the roster (float). Used for calculating budget-adjusted dollar value of the player (default 200.0)",
                    },
                },
                "required": ["player_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_player_to_roster",
            "description": "Add a player to the roster. Validates budget, and prevents duplicates.",
            "parameters": {
                "type": "object",
                "properties": {
                    # "session_id": {
                    #     "type": "string",
                    #     "description": "The session ID",
                    # },
                    "player_id": {
                        "type": "integer",
                        "description": "The player ID to add",
                    },
                    "budget": {
                        "type": "number",
                        "description": "Total budget allotted for the roster (float). Used for calculating budget-adjusted dollar value of the player (default 200.0)",
                    },
                },
                "required": ["player_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_player_from_roster",
            "description": "Remove a player from the roster by their full name.",
            "parameters": {
                "type": "object",
                "properties": {
                    # "session_id": {
                    #     "type": "string",
                    #     "description": "The session ID",
                    # },
                    "player_name": {
                        "type": "string",
                        "description": "The full name of the player to remove",
                    },
                },
                "required": ["player_name"],
            },
        },
    },
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "find_replacements",
    #         "description": "Find replacement players for a specific position, optionally excluding certain players and filtering by cost.",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {
    #                 "position": {
    #                     "type": "string",
    #                     "description": "Position to find replacements for (PG, SG, SF, PF, C)",
    #                 },
    #                 "exclude_player_ids": {
    #                     "type": "array",
    #                     "items": {"type": "integer"},
    #                     "description": "List of player IDs to exclude from results",
    #                 },
    #                 "budget": {
    #                     "type": "number",
    #                     "description": "Total budget for calculating dollar values (default 200)",
    #                 },
    #                 "max_cost": {
    #                     "type": "number",
    #                     "description": "Maximum dollar value/cost for replacements",
    #                 },
    #                 "limit": {
    #                     "type": "integer",
    #                     "description": "Maximum number of results (default 10)",
    #                 },
    #             },
    #             "required": [],
    #         },
    #     },
    # },
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "tool_get_cached_player_stats",
    #         "description": "Get cached player stats from the stored player data. This is faster than fetching from the API and should be used for regular operations. Returns a list of active players and their season statistics.",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {},
    #             "required": [],
    #         },
    #     },
    # },
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "tool_fetch_player_stats",
    #         "description": "Fetch player stats from NBA API and refresh the cache. This is slow and should only be used to refresh the player pool. For regular operations, use tool_get_cached_player_stats instead.",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {},
    #             "required": [],
    #         },
    #     },
    # },
]

# System prompt for ReAct agent
SYSTEM_PROMPT = """You are an intelligent, helpful assistant that builds fantasy NBA rosters of 12 players using the ReAct (Reasoning and Acting) pattern.

WORKFLOW (ReAct Pattern):
1. **Thought**: State what you'll do next in 1-2 brief sentences
2. **Action**: Call the appropriate tool
3. **Observation**: Note the result in 1-2 sentences, then proceed

ROSTER BUILDING PROTOCOL:
Step 1: Call get_current_roster to check available slots
Step 2: Call search_roster_players with count=[number of slots to be filled] to get player IDs that fit search budget. If user requests roster without specifying count, fill all remaining slots
Step 3: Call add_player_to_roster for each player ID sequentially.
Step 4: Confirm completion

NOTES:
- If user asks to add a player by name, fetch their id by calling get_player_details first.
- If user asks to remove a player, fetch their information by calling get_current_roster first.
- If players have been added or removed, always tell the user who were added or removed.

REASONING DEPTH CONTROL:
- Use minimal reasoning for routine operations (checking roster, adding players)
- Never reason about what to say to the user
- Stop reasoning immediately after deciding on an action
- IMPORTANT: Keep all reasoning under 3 sentences. Never more than 3 sentences.

EFFICIENCY RULES:
- No meta-commentary about "what we should tell the user"
- No reasoning loops or self-dialogue

Note: Player data is cached and periodically updated."""


def _summarize_reasoning(reasoning_content: str) -> str:
    """Summarize agent reasoning_content into a 1-2 line summary using another model."""
    try:
        response = client.chat.completions.create(
            model="liquid/lfm-2.2-6b",
            messages=[
                {"role": "system", "content": "Summarize the following agent reasoning into a concise 1-2 line summary. Focus on the core intent and next steps."},
                {"role": "user", "content": reasoning_content}
            ],
            temperature=0.3,
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error summarizing reasoning: {e}")
        return reasoning_content[:200] + "..." # Fallback to truncated original


class ReActAgent:
    """ReAct agent for fantasy NBA roster management."""

    def __init__(
        self,
        session_id: str,
        model: str = "openai/gpt-oss-120b",#"nvidia/nemotron-3-nano-30b-a3b:free",
        temperature: float = 0.0,
        max_iterations: int = 20,
    ):
        self.session_id = session_id
        self.model = model
        self.temperature = temperature
        self.max_iterations = max_iterations
        self.activity_log: List[Dict[str, str]] = []

    def _add_activity(self, step: str, status: str, detail: str) -> None:
        """Add an activity to the log."""
        self.activity_log.append({"step": step, "status": status, "detail": detail})

    def _call_api(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None) -> Any:
        """Make an HTTP call to the API endpoint."""
        url = f"{API_BASE_URL}{endpoint}"
        try:
            with httpx.Client(timeout=30.0) as client:
                if method == "GET":
                    response = client.get(url, params=params)
                elif method == "POST":
                    response = client.post(url, params=params, json=json_data)
                elif method == "DELETE":
                    response = client.delete(url, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            return {"error": f"API call failed: {str(e)}"}

    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool function by calling API endpoints."""
        # Get current roster to extract budget and slots if needed
        # roster_response = self._call_api("GET", f"/roster/{self.session_id}")
        # budget = roster_response.get("budget", 200.0) if isinstance(roster_response, dict) else 200.0
        # slots = roster_response.get("slots", 12) if isinstance(roster_response, dict) else 12

        try:
            if tool_name == "get_current_roster":
                result = self._call_api("GET", f"/roster/{self.session_id}")
                # Convert CurrentRoster format to expected dict format
                if isinstance(result, dict) and "players" in result:
                    csv_lines = ["players:", "pid,name,team,pos,fpg,val,score"]
                    for p in result.get("players", []):
                        csv_lines.append(
                            f"{p.get('player_id', 0)},{p.get('name', '')},{p.get('team', '')},{p.get('position', 'none')},{p.get('fpg', 0.0)},{p.get('dollar_value', 0.0)},{p.get('score', 0.0)}"
                        )
                    
                    total_cost = result.get("total_cost", 0.0)
                    budget = result.get("budget", 200.0)
                    
                    result = "\n".join(csv_lines) + f"\n\ntotal_cost: {total_cost}\nbudget: {budget}"
                self._add_activity(
                    "Tool: get_current_roster",
                    "success",
                    f"Retrieved current roster",
                )
                return result

            elif tool_name == "search_roster_players":
                params = {
                    "session_id": arguments.get("session_id", self.session_id),
                    "search_budget": arguments.get("search_budget", 200.0),
                    "budget": arguments.get("budget", 200.0),
                    "count": arguments.get("count", 1),
                }
                # Remove None values
                params = {k: v for k, v in params.items() if v is not None}
                result = self._call_api("GET", "/players/search-roster", params=params)
                if isinstance(result, dict) and result.get("success"):
                    player_count = len(result.get("player_ids", []))
                    self._add_activity(
                        "Tool: search_roster_players",
                        "success",
                        f"Found {player_count} suitable players for the roster",
                    )
                else:
                    self._add_activity(
                        "Tool: search_roster_players",
                        "error",
                        result.get("error", "Unknown error"),
                    )
                return result

            elif tool_name == "get_player_details":
                params = {
                    "budget": arguments.get("budget", 200.0),
                }
                result = self._call_api("GET", f"/players/{arguments['player_name']}", params=params)
                self._add_activity(
                    "Tool: get_player_details",
                    "success" if result.get("success") else "error",
                    result.get("error", f"Retrieved details for player {arguments['player_name']}"),
                )
                return result

            elif tool_name == "add_player_to_roster":
                json_data = {
                    "player_id": arguments["player_id"],
                    "budget": arguments.get("budget", 200.0),
                }
                result = self._call_api("POST", f"/roster/{self.session_id}/players", json_data=json_data)
                self._add_activity(
                    "Tool: add_player_to_roster",
                    "success" if result.get("success") else "error",
                    result.get("error", result.get("message", "Player added successfully")),
                )
                return result

            elif tool_name == "remove_player_from_roster":
                result = self._call_api("DELETE", f"/roster/{self.session_id}/players/{arguments['player_name']}")
                self._add_activity(
                    "Tool: remove_player_from_roster",
                    "success" if result.get("success") else "error",
                    result.get("error", result.get("message", "Player removed successfully")),
                )
                return result

            # elif tool_name == "find_replacements":
            #     params = {
            #         "position": arguments.get("position"),
            #         "budget": arguments.get("budget", budget),
            #         "max_cost": arguments.get("max_cost"),
            #         "limit": arguments.get("limit", 10),
            #     }
            #     # Handle exclude_player_ids
            #     exclude_ids = arguments.get("exclude_player_ids")
            #     if exclude_ids:
            #         params["exclude_player_ids"] = exclude_ids
            #     # Remove None values
            #     params = {k: v for k, v in params.items() if v is not None}
            #     result = self._call_api("GET", "/players/replacements", params=params)
            #     if isinstance(result, list):
            #         self._add_activity(
            #             "Tool: find_replacements",
            #             "success",
            #             f"Found {len(result)} replacement options",
            #         )
            #     else:
            #         self._add_activity(
            #             "Tool: find_replacements",
            #             "error",
            #             result.get("error", "Unknown error"),
            #         )
            #     return result

            # elif tool_name == "tool_get_cached_player_stats":
            #     # Call the API endpoint which will use cached data
            #     result = self._call_api("POST", "/tools/get-cached-player-stats", json_data={})
            #     if isinstance(result, dict) and "players" in result:
            #         self._add_activity(
            #             "Tool: tool_get_cached_player_stats",
            #             "success",
            #             f"Retrieved cached stats for {len(result.get('players', []))} players",
            #         )
            #     else:
            #         self._add_activity(
            #             "Tool: tool_get_cached_player_stats",
            #             "error",
            #             result.get("error", "No cached data available. Please refresh player stats first."),
            #         )
            #     return result
            
            # elif tool_name == "tool_fetch_player_stats":
            #     result = self._call_api("POST", "/tools/fetch-player-stats", json_data={})
            #     if isinstance(result, dict) and "players" in result:
            #         self._add_activity(
            #             "Tool: tool_fetch_player_stats",
            #             "success",
            #             f"Fetched and cached stats for {len(result.get('players', []))} players",
            #         )
            #     else:
            #         self._add_activity(
            #             "Tool: tool_fetch_player_stats",
            #             "error",
            #             result.get("error", "Unknown error"),
            #         )
            #     return result


            else:
                error_msg = f"Unknown tool: {tool_name}"
                self._add_activity(f"Tool: {tool_name}", "error", error_msg)
                return {"error": error_msg}

        except Exception as e:
            error_msg = f"Error executing {tool_name}: {str(e)}"
            self._add_activity(f"Tool: {tool_name}", "error", error_msg)
            return {"error": error_msg}

    def execute(
        self,
        user_message: str,
        budget: Optional[float] = None,
        dry_run: bool = False,
        stream_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """Execute the ReAct agent loop."""
        # Initialize or update roster with budget if provided
        # if budget is not None:
        #     roster_response = self._call_api("GET", f"/roster/{self.session_id}")
        #     if isinstance(roster_response, dict):
        #         roster_data = {
        #             "players": [
        #                 {
        #                     "player_id": p.get("player_id", 0),
        #                     "name": p.get("name", ""),
        #                     "team": p.get("team"),
        #                     "position": p.get("position"),
        #                     "fpg": p.get("fpg", 0.0),
        #                     "dollar_value": p.get("dollar_value", 0.0),
        #                     "score": p.get("score", 0.0),
        #                 }
        #                 for p in roster_response.get("players", [])
        #             ],
        #             "budget": roster_response.get("budget", 200.0),
        #             "slots": roster_response.get("slots", 12),
        #         }
        #         update_session_roster(
        #             self.session_id,
        #             roster_data.get("players", []),
        #             budget,
        #             roster_data.get("slots", 12),
        #         )

        # Load conversation history
        #messages = get_session_messages(self.session_id)
        
        # Initialize messages if empty
        #if not messages:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        save_session_messages(self.session_id, messages)

        # Add user message
        messages.append({"role": "user", "content": user_message})
        append_session_message(self.session_id, "user", user_message)

        #self._add_activity("User Input", "success", f"Received: {user_message}")

        # ReAct loop
        iteration = 0
        final_response = None

        while iteration < self.max_iterations:
            iteration += 1
            #self._add_activity("Iteration", "info", f"Starting iteration {iteration}")

            try:
                # Call OpenAI API
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    temperature=self.temperature,
                    extra_body={
                        "reasoning": {
                            "effort": "low"
                        }
                    },
                )

                message = response.choices[0].message
                reasoning_content = getattr(response.choices[0].message, 'reasoning', None)
                
                # Add assistant's reasoning/response to messages
                assistant_content = message.content or ""
                if assistant_content:
                    messages.append({"role": "assistant", "content": assistant_content})
                    #self._add_activity("Reasoning", "success", assistant_content)
                    # if stream_callback:
                    #     stream_callback({"type": "reasoning", "content": assistant_content})
                if reasoning_content:
                    logger.info(f"Reasoning: {reasoning_content}")
                    reasoning_content = _summarize_reasoning(reasoning_content)
                    self._add_activity("Reasoning", "success", reasoning_content)
                    if stream_callback:
                        stream_callback({"type": "reasoning", "content": reasoning_content})
                
                # Prune messages to keep token usage reasonable before any next API call (TO-DO)
                #messages = self._prune_messages(messages, max_messages=18)

                # Check if agent wants to use a tool
                if message.tool_calls:
                    for tool_call in message.tool_calls:
                        tool_name = tool_call.function.name
                        try:
                            arguments = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError:
                            arguments = {}

                        # Add tool call to messages
                        messages.append(
                            {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": tool_call.id,
                                        "type": "function",
                                        "function": {
                                            "name": tool_name,
                                            "arguments": tool_call.function.arguments,
                                        },
                                    }
                                ],
                            }
                        )

                        self._add_activity(
                            "Action",
                            "info",
                            f"Calling tool: {tool_name} with args: {json.dumps(arguments)}",
                        )
                        
                        # Execute tool
                        tool_result = self._execute_tool(tool_name, arguments)
                        
                        if stream_callback:
                            # Check if tool execution was successful for the action event
                            is_tool_success = True
                            if isinstance(tool_result, dict) and "error" in tool_result:
                                is_tool_success = False
                            
                            stream_callback({
                                "type": "action", 
                                "tool": tool_name, 
                                "arguments": arguments,
                                "status": "success" if is_tool_success else "error",
                                "message": tool_result.get("error") if isinstance(tool_result, dict) else None
                            })

                        # Add tool result to messages
                        messages.append(
                            {
                                "role": "tool",
                                "content": tool_result if isinstance(tool_result, str) else json.dumps(tool_result),
                                "tool_call_id": tool_call.id,
                            }
                        )

                        self._add_activity(
                            "Observation",
                            "success",
                            f"Tool {tool_name} returned successfully",
                        )
                        logger.info(f"Tool {tool_name} was called with arguments: {json.dumps(arguments)} and returned: {tool_result}")
                        
                        if stream_callback:
                            stream_callback({"type": "observation", "tool": tool_name, "result": tool_result})
                            
                            # Emit roster update if the tool modified the roster
                            if tool_name in ["add_player_to_roster", "remove_player_from_roster"]:
                                # We need to check if the tool result indicates success
                                is_success = False
                                if isinstance(tool_result, dict):
                                    is_success = tool_result.get("success", False)
                                elif isinstance(tool_result, str):
                                    try:
                                        res_dict = json.loads(tool_result)
                                        is_success = res_dict.get("success", False)
                                    except:
                                        pass
                                
                                if is_success:
                                    roster_data = self._call_api("GET", f"/roster/{self.session_id}")
                                    if isinstance(roster_data, dict) and "players" in roster_data:
                                        stream_callback({"type": "roster_update", "players": roster_data["players"]})

                else:
                    # No tool calls, agent is done
                    final_response = assistant_content or "Task completed."
                    break

            except Exception as e:
                error_msg = f"Error in iteration {iteration}: {str(e)}"
                self._add_activity("Error", "error", error_msg)
                messages.append(
                    {
                        "role": "assistant",
                        "content": f"I encountered an error: {error_msg}. Let me try a different approach.",
                    }
                )
                if iteration >= self.max_iterations:
                    final_response = f"Reached maximum iterations. Last error: {error_msg}"
                    break

        # Save final messages
        save_session_messages(self.session_id, messages)
        if final_response:
            append_session_message(self.session_id, "assistant", final_response)

        # Get final roster state
        # roster_response = self._call_api("GET", f"/roster/{self.session_id}")
        # final_roster = {
        #     "players": [
        #         {
        #             "player_id": p.get("player_id", 0),
        #             "name": p.get("name", ""),
        #             "team": p.get("team"),
        #             "position": p.get("position"),
        #             "fpg": p.get("fpg", 0.0),
        #             "dollar_value": p.get("dollar_value", 0.0),
        #             "score": p.get("score", 0.0),
        #         }
        #         for p in roster_response.get("players", [])
        #     ],
        #     "total_cost": roster_response.get("total_cost", 0.0),
        #     "budget": roster_response.get("budget", 200.0),
        #     "slots": roster_response.get("slots", 12),
        #     "slots_remaining": roster_response.get("slots_remaining", 12),
        # } if isinstance(roster_response, dict) else {"players": [], "total_cost": 0.0, "budget": 200.0, "slots": 12, "slots_remaining": 12}
        
        # Load preferences used
        #preferences = load_preferences()

        return {
            "session_id": self.session_id,
            "plan": [activity["step"] for activity in self.activity_log],
            "activity_log": self.activity_log,
            #"roster": final_roster,
            #"report_path": report_path,
            #"knowledge_used": preferences,
            "message": final_response or "Agent execution completed.",
        }
