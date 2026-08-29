# Raven Sprint 1

This version preserves Raven's existing Ollama chat, recent conversation
history and long-term memory. It adds the first product foundation:

- persistent student profiles;
- guided onboarding through `/start` or `/setup`;
- `/profile` and `/menu` commands;
- clickable navigation for Raven's five product pillars;
- honest placeholders for modules planned in later sprints;
- centralized configuration and structured logging;
- SQLite connection safety settings and input validation.

## Project files

- `bot.py` — Telegram handlers, onboarding, menus and Ollama chat.
- `memory.py` — SQLite schema and database functions.
- `config.py` — environment settings and validation.
- `keyboards.py` — reusable Telegram inline keyboards.
- `tests/test_memory.py` — database tests.

## Install

Open PowerShell inside this folder and create a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

Copy `.env.example` to `.env`, then insert your real Telegram token and Ollama
model name. Never commit `.env` to GitHub.

## Run

Make sure Ollama is running and the configured model is installed, then use:

```powershell
py bot.py
```

Open the bot in Telegram and send `/start`. Existing `messages` and `memories`
tables remain compatible. The new `student_profiles` table is created
automatically when Raven starts.

## Commands

- `/start` — begin onboarding or open Raven.
- `/setup` — create or update the student profile.
- `/profile` — view the current profile.
- `/menu` — open the main feature menu.
- `/remember <text>` — save a long-term memory.
- `/memories` — list memories.
- `/forget <id>` — delete one memory.
- `/forgetall CONFIRM` — delete all memories.
- `/reset` — clear recent chat history only.
- `/cancel` — cancel profile setup.

## Next sprint

Sprint 2 will build the first working Academic module: Exam Rescue. It should
start with one JSS CSE semester and a manually verified resource dataset before
automatic scraping is added.
