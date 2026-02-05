# NBA Fantasy Team Builder Agent

A full-stack application for building and managing NBA fantasy rosters using intelligent AI agents.

## Tech Stack

- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS, Radix UI.
- **Backend**: Python, FastAPI, SQLite (for session and roster persistence).
- **AI/LLM**: OpenAI SDK (via OpenRouter), GPT OSS 120B in production, Nvidia Nemotron 3 Nano for development, Light models (Liquid AI) for reasoning summarization, ReAct reasoning pattern.
- **Data**: `nba_api` for real-time player statistics and profiles.

## Agent Architecture

The project uses a **ReAct (Reasoning and Acting)** architecture for its agents:

1. **Reasoning (Thought)**: The agent analyzes the user's request and plans the next step.
2. **Acting (Action)**: The agent executes specific tools (e.g., searching players, adding to roster, fetching stats) via API endpoints.
3. **Observation**: The agent receives the tool's output and updates its internal state.
4. **Loop**: This process repeats until the goal (e.g., a complete 12-player roster) is achieved.

Key features include real-time streaming of agent reasoning, budget-aware player valuation, and persistent session management via a SQLite database.

### Agent Implementation Details

- A single tool-using LLM agent powered by OpenAI GPT models (via OpenRouter), utilizing OpenAI's function calling API for tool execution.
- The agent maintains persistent session state with SQLite-backed conversation history and activity logging. 
- Employs 5 core tools for roster management: roster inspection, player search, detailed player lookup, player addition/removal, with all tools executed via HTTP API calls to maintain clean separation between agent logic and data operations.
- The agent uses deterministic reasoning (temperature=0.0) with a maximum of 20 iterations per task, and includes reasoning summarization for efficient streaming.
