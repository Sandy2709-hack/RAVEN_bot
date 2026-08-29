# Raven Sprint 2 — COA Exam Rescue

Sprint 2 preserves Raven's Ollama chat, conversation history, long-term memory,
student onboarding and five-pillar menu. It adds Raven's first complete
Academic workflow for Semester 3 COA (`BCS302`).

## New in Sprint 2

- official AKTU COA syllabus stored as structured JSON;
- syllabus and Gateway resource browsers inside Telegram;
- Exam Rescue conversation flow;
- input validation for days and daily study hours;
- completed-unit selection using Telegram buttons;
- selectable 40+, 50+, 60+ and 70+ targets;
- deterministic study-plan generation without using Ollama;
- time-budgeted daily schedules and final revision blocks;
- saved plans in SQLite;
- `/lastplan` to retrieve the latest plan;
- transparent `syllabus-based, not yet PYQ-verified` labels.

## Project files

- `bot.py` — Telegram commands, conversations, menus and Ollama chat.
- `academics.py` — COA dataset loading and Exam Rescue algorithm.
- `memory.py` — SQLite schema, profiles, memories and saved plans.
- `keyboards.py` — reusable inline keyboards.
- `config.py` — environment settings and validation.
- `data/coa_bcs302.json` — official syllabus topics and Gateway links.
- `tests/` — database and planning-algorithm tests.

## Upgrade safely from Sprint 1

1. Stop Raven with `CTRL+C`.
2. Make a backup or Git commit of your working Sprint 1 folder.
3. Replace the Python, README and requirements files with the Sprint 2 files.
4. Add the new `data` folder.
5. Keep your existing `.env` and `raven_memory.db`.
6. Run `py -m pip install -r requirements.txt` inside the active environment.
7. Start Raven with `py bot.py`.

`init_db()` creates the new `exam_rescue_plans` table automatically. Existing
messages, memories and student profiles remain compatible.

## Fresh installation

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and insert your real Telegram token and Ollama
model. Never commit `.env` to GitHub.

Make sure Ollama is running, then start Raven:

```powershell
py bot.py
```

## Test Exam Rescue

1. Send `/menu`.
2. Select **Academics**.
3. Select **COA Exam Rescue**.
4. Enter remaining days.
5. Enter realistic daily hours.
6. Select completed units and press **Continue**.
7. Choose a target score.
8. Use `/lastplan` to retrieve the saved plan.

## Commands

- `/start` — begin onboarding or open Raven.
- `/setup` — create or update the student profile.
- `/profile` — view the current profile.
- `/menu` — open the feature menu.
- `/lastplan` — retrieve the latest COA rescue plan.
- `/remember <text>` — save a long-term memory.
- `/memories` — list memories.
- `/forget <id>` — delete one memory.
- `/forgetall CONFIRM` — delete all memories.
- `/reset` — clear recent chat history only.
- `/cancel` — cancel onboarding or Exam Rescue.

## Data limitations

The syllabus source and Gateway unit mapping are verified. Topic ordering and
time allocation are currently syllabus-based planning heuristics. Raven does
not claim PYQ frequency until a later collector indexes and validates enough
question papers.

## Next sprint

Sprint 2B will collect public COA question papers, extract questions, map them
to official topics and replace heuristic coverage weights with real repeat and
marks data.
