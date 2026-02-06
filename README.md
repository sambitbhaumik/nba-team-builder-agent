# NBA Fantasy Team Builder Agent

A full-stack application for building and managing NBA fantasy rosters using intelligent AI agents. 

## Quick Start (One-Command Run)

To get the project up and running quickly, follow these steps:

### 1. Setup
Run the setup script to create a virtual environment, install Python dependencies, and install npm packages.

**Windows (PowerShell):**
```powershell
.\setup.ps1
```

**macOS/Linux:**
```bash
chmod +x setup.sh run.sh
./setup.sh
```

### 2. Run
Start both the FastAPI backend and Vite frontend with a single command.

**Windows (PowerShell):**
```powershell
.\run.ps1
```

**macOS/Linux:**
```bash
./run.sh
```

- **Frontend**: [http://localhost:5173](http://localhost:5173)
- **Backend**: [http://localhost:8000](http://localhost:8000)

> **Note**: An `OPENROUTER_API_KEY` is required in a `.env` file within the `backend/` directory for the AI agent to function.

---

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

<img width="2818" height="1753" alt="image" src="https://github.com/user-attachments/assets/cd322d45-8843-4baa-895b-c33757f2135f" />
