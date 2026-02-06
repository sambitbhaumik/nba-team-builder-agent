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
    save_session_messages,
    get_session_messages,
    create_pending_approval,
    get_latest_pending_approval,
    update_approval_status,
)

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
            "name": "fetch_user_preferences",
            "description": "Fetch all stored user preferences from the database. Use this to understand user tastes and apply them when selecting players.",
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
                "required": ["count"],
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
            "description": "Add one or more players to the roster. Validates budget, and prevents duplicates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "player_ids": {
                        "type": "array",
                        "items": {
                            "type": "integer"
                        },
                        "description": "List of player IDs to add",
                    },
                    "budget": {
                        "type": "number",
                        "description": "Total budget allotted for the roster (float). Used for calculating budget-adjusted dollar value of the player (default 200.0)",
                    },
                },
                "required": ["player_ids"],
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
                    "player_name": {
                        "type": "string",
                        "description": "The full name of the player to remove",
                    },
                },
                "required": ["player_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_roster_budget",
            "description": "Modify the budget allotted for the current roster.",
            "parameters": {
                "type": "object",
                "properties": {
                    "budget": {
                        "type": "number",
                        "description": "The new budget amount (float) allotted for the roster.",
                    },
                },
                "required": ["budget"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_user_preference",
            "description": "Save a user preference to the database. Preferences can be anything related to the user's sports interests, like preferred teams, player attributes they value (e.g., 'high 3pt', 'good rebounders'), etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "The type of preference (e.g., 'preferred_team', 'player_attribute')",
                    },
                    "value": {
                        "type": "string",
                        "description": "The specific preference value (e.g., 'Lakers', 'high 3pt')",
                    },
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_approval",
            "description": "Request user approval for a proposed roster change. Use this when you need to replace players to make room for improvements. Provide a clear summary of what you're proposing to do.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action_type": {
                        "type": "string",
                        "enum": ["remove_and_replace"],
                        "description": "Type of action requiring approval",
                    },
                    "players_to_remove": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of player names to remove from roster",
                    },
                    "players_to_add": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of player names being added to roster",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Explanation of why these changes improve the roster (e.g., 'Removing low-rebound players to add higher-rebound players per your request')",
                    },
                },
                "required": ["action_type", "players_to_remove", "players_to_add", "reason"],
            },
        },
    },
]

# System prompt for ReAct agent
SYSTEM_PROMPT = """You are an intelligent, helpful assistant that builds fantasy NBA rosters of 8 players using the ReAct (Reasoning and Acting) pattern.
WORKFLOW (ReAct Pattern):
1. **Thought**: State what you'll do next in 1-2 brief sentences
2. **Action**: Call the appropriate tool
3. **Observation**: Note the result in 1-2 sentences, then proceed

ROSTER BUILDING PROTOCOL:
Step 1: Call get_current_roster to check roster state.
Step 2: Call fetch_user_preferences to fetch user's stored preferences.
Step 3: Analyze the situation:
   - If roster has empty slots → proceed to fill them
   - If roster is full and user wants to add players → this is a REPLACEMENT SCENARIO
Step 4: Determine which players to add based on preferences:
   
   IF no stored user preferences exist:
   a) Call search_roster_players with count=[number of slots to be filled]
   b) If user does not specify a count, fill all remaining slots in the roster
   c) Proceed directly to Step 4 with all returned players
   
   IF stored user preferences exist:
   a) Call search_roster_players with count=10
   b) Use your judgment to select the best 2 players from this list based on user preferences
   c) If unsatisfied with the options, fall back to the "no preferences" approach above

Step 5: IMPORTANT: For EACH player you've decided to add:
   - You must call add_player_to_roster with that player ID or IDs for multiple players
   - Do NOT assume players are added automatically

Step 4: Confirm completion to the user.

KNOWLEDGE & PREFERENCES:
- If the user mentions a basketball related preferences (e.g., "I like the Lakers", "I want more 3pt shooters", "Focus on rebounders"), call save_user_preference to store it.
- Store them with simple key-value pairs. Example: "preferred_team": "Lakers", "player_attribute": "high 3pt". Consider storing only stats, team and player related preferences.
- If they only intend to add preferences, then do not start building roster. Only save preferences. Build rosters if they say so.

NOTES:
- If a new budget has been provided, always set that first with update_roster_budget before proceeding with the next step.
- If user asks to add a player by name, fetch their id by calling get_player_details first.
- If user asks to remove a player, verify player is in the roster by calling get_current_roster first.
- If players have been added or removed, always tell the user who were added or removed.
- Never choose more than 2 players based on user preferences. We do this to keep the roster balanced.
- IF you have to add players and the roster is full or replace a player (REPLACEMENT SCENARIO):
   a) We support ONLY ONE replacement at the moment.
   b) Identify which player you want to remove from the roster and which to add. Use tools to get all information (Fetch 10 players from search_roster_players) before using your judgement on who to add. 
   c) Call request_approval with the specific player to add (must be valid player found from search_roster_players) and remove, and your reasoning.
   d) Wait for the user's response.
   e) ONLY if the user approves, proceed to call remove_player_from_roster and then add_player_to_roster.
   f) If the user rejects, do NOT remove or add any player. Inform the user you will not proceed with the replacement.

REASONING DEPTH CONTROL:
- Use minimal reasoning for routine operations (checking roster, loading preferences)
- Reason deeply when selecting players or handling replacement, but keep it within 10 sentences. 
- Never reason about what to say to the user
- No reasoning loops or self-dialogue.

PREPARING FINAL RESPONSE:
- IMPORTANT: Recall if you added any player based on user preferences, you MUST include a 1-2 line summary of which players you chose based on which preferences. Wrap this knowledge-based reasoning in a <knowledge_reasoning> tag.
  Example: <knowledge_reasoning>I chose Stephen Curry and Klay Thompson because you preferred high 3pt shooters.</knowledge_reasoning>
"""


def _summarize_reasoning(reasoning_content: str) -> str:
    """Summarize agent reasoning_content into a 1-2 line summary using another model."""
    try:
        response = client.chat.completions.create(
            model="liquid/lfm-2.5-1.2b-instruct:free",
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
                elif method == "PATCH":
                    response = client.patch(url, params=params, json=json_data)
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
        try:
            if tool_name == "get_current_roster":
                result = self._call_api("GET", f"/roster/{self.session_id}")
                # Convert CurrentRoster format to expected dict format
                if isinstance(result, dict) and "players" in result:
                    csv_lines = ["players found:", "player_id,name,team,fpg,val,pts,reb,ast,stl,blk,tov,fg_pct,fg3_pct,age"]
                    for p in result.get("players", []):
                        csv_lines.append(
                            f"{p.get('player_id', 0)},{p.get('name', '')},{p.get('team', '')},{p.get('fpg', 0.0)},{p.get('dollar_value', 0.0)},{p.get('pts', 0.0)},{p.get('reb', 0.0)},{p.get('ast', 0.0)},{p.get('stl', 0.0)},{p.get('blk', 0.0)},{p.get('tov', 0.0)},{p.get('fg_pct', 0.0)},{p.get('fg3_pct', 0.0)},{p.get('age', 0)}"
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

            elif tool_name == "fetch_user_preferences":
                result = self._call_api("GET", "/knowledge/preferences")
                if isinstance(result, dict) and "items" in result:
                    items = result.get("items", [])
                    preference_count = len(items)
                    
                    if preference_count > 0:
                        preference_lines = ["user preferences:"]
                        for item in items:
                            key = item.get("key", "")
                            value = item.get("value", "")
                            preference_lines.append(f"{key}: {value}")
                        result = "\n".join(preference_lines)
                    else:
                        result = "No user preferences stored."
                    
                    self._add_activity(
                        "Tool: fetch_user_preferences",
                        "success",
                        f"Retrieved {preference_count} user preferences",
                    )
                else:
                    self._add_activity(
                        "Tool: fetch_user_preferences",
                        "error",
                        result.get("error", "Unknown error"),
                    )
                    result = {"error": result.get("error", "Unknown error")}
                return result

            elif tool_name == "save_user_preference":
                json_data = {
                    "key": arguments["key"],
                    "value": arguments["value"],
                }
                result = self._call_api("POST", "/knowledge/add", json_data=json_data)
                self._add_activity(
                    "Tool: save_user_preference",
                    "success" if result.get("status") == "saved" else "error",
                    result.get("error", "Preference saved successfully" if result.get("status") == "saved" else "Unknown error"),
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
                    players = result.get("players", [])
                    player_count = len(players)
                    
                    csv_lines = ["players found:", "player_id,name,team,fpg,val,pts,reb,ast,stl,blk,tov,fg_pct,fg3_pct,age"]
                    for p in players:
                        csv_lines.append(
                            f"{p.get('player_id', 0)},{p.get('name', '')},{p.get('team', '')},{p.get('fpg', 0.0)},{p.get('dollar_value', 0.0)},{p.get('pts', 0.0)},{p.get('reb', 0.0)},{p.get('ast', 0.0)},{p.get('stl', 0.0)},{p.get('blk', 0.0)},{p.get('tov', 0.0)},{p.get('fg_pct', 0.0)},{p.get('fg3_pct', 0.0)},{p.get('age', 0)}"
                        )
                    
                    result = "\n".join(csv_lines)
                    
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
                    "player_ids": arguments["player_ids"],
                    "budget": arguments.get("budget", 200.0),
                }
                result = self._call_api("POST", f"/roster/{self.session_id}/players", json_data=json_data)
                self._add_activity(
                    "Tool: add_player_to_roster",
                    "success" if result.get("success") else "error",
                    result.get("error", result.get("message", "Players added successfully")),
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

            elif tool_name == "update_roster_budget":
                json_data = {
                    "budget": arguments["budget"],
                }
                result = self._call_api("PATCH", f"/roster/{self.session_id}/budget", json_data=json_data)
                self._add_activity(
                    "Tool: update_roster_budget",
                    "success" if result.get("success") else "error",
                    result.get("error", result.get("message", "Budget updated successfully")),
                )
                return result

            elif tool_name == "request_approval":
                approval_id = str(uuid4())
                details = {
                    "players_to_remove": arguments["players_to_remove"],
                    "players_to_add": arguments["players_to_add"],
                    "reason": arguments["reason"]
                }
                create_pending_approval(
                    approval_id=approval_id,
                    session_id=self.session_id,
                    action_type=arguments["action_type"],
                    details=details
                )
                
                self._add_activity(
                    "Action",
                    "info",
                    f"Requesting approval to remove {arguments['players_to_remove']} and add {arguments['players_to_add']}"
                )
                
                return {
                    "status": "awaiting_approval",
                    "approval_id": approval_id,
                    "message": f"User approval requested for: {arguments['reason']}. Please wait for the user to approve or reject this action."
                }

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
        approval_response: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute the ReAct agent loop."""

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                
        # Check for pending approvals if this is a new message (not an approval response)
        if not approval_response:
            pending = get_latest_pending_approval(self.session_id)
            if pending:
                # If there's a pending approval, we should probably warn the user or handle it
                # For now, we'll just proceed, but the agent might see it in history if we added it
                pass

        # save_session_messages(self.session_id, messages)

        # Add user message or approval response
        if approval_response:
            approval_id = approval_response.get("approval_id")
            approved = approval_response.get("approved", False)
            status = "APPROVED" if approved else "REJECTED"
            
            # Fetch the last 5 messages if it's an approval response to avoid context bloat
            messages.extend(get_session_messages(self.session_id, limit=4))
            # Update status in DB
            update_approval_status(approval_id, "approved" if approved else "rejected")
            
            content = f"[SYSTEM] User has {status} your request (ID: {approval_id}). "
            if approved:
                content += "You may now proceed with the players removal and addition as planned."
            else:
                content += "Do NOT proceed with the removal or addition. Inform the user you are cancelling the replacement."
            
            messages.append({"role": "user", "content": content})
            append_session_message(self.session_id, "user", content)
        else:
            messages.append({"role": "user", "content": user_message})
            append_session_message(self.session_id, "user", user_message)

        # ReAct loop
        iteration = 0
        final_response = None

        while iteration < self.max_iterations:
            iteration += 1

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
                            "effort": "high"
                        }
                    },
                )

                message = response.choices[0].message
                # fetch reasoning content from the response
                reasoning_content = getattr(response.choices[0].message, 'reasoning', None)
                
                # Add assistant's response to messages
                assistant_content = message.content or ""
                if assistant_content:
                    messages.append({"role": "assistant", "content": assistant_content})
                    
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

        return {
            "session_id": self.session_id,
            "plan": [activity["step"] for activity in self.activity_log],
            "activity_log": self.activity_log,
            "message": final_response or "Agent execution completed.",
        }
