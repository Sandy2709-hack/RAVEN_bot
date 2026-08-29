# Raven Sprint 2.3 — Complete Semester 3 Academic Catalog

Sprint 2.3 keeps Raven's Ollama chat, memory, student onboarding and reusable
Academic hierarchy. It activates five Semester 3 subjects across Exam Rescue,
Syllabus and Resources.

## Available subjects

| Code | Subject | Starter-resource provider |
| --- | --- | --- |
| `BCS301` | Data Structure | Gateway Classes |
| `BCS302` | Computer Organization and Architecture (COA) | Gateway Classes |
| `BAS301` | Technical Communication | Gateway Classes |
| `BCC301` | Cyber Security | Gateway Classes |
| `BCS303` | Discrete Structures and Theory of Logic (DSTL) | Multi Atoms Plus |

The subject codes and unit topics follow AKTU's official 2023-24 syllabus
documents. Every resource is free and mapped to a syllabus unit. Resource
ordering and rescue-plan allocation remain syllabus-based; Raven does not
claim PYQ frequency until enough question papers have been collected and
validated.

## Academic flow

1. Open **Academics**.
2. Choose **Exam Rescue**, **Syllabus** or **Resources**.
3. Choose one of the five subjects available for CSE Semester 3.
4. For Exam Rescue, enter the remaining days, select completed units and pick
   a target of 40+, 50+, 60+ or 70+.
5. Raven automatically chooses the pace and creates a deterministic daily plan.

The planner deliberately asks for days, not hours. It calculates a practical
daily workload from urgency and target score, schedules unit-level study blocks
and keeps the final revision block inside the total time budget.

## Project files

- `bot.py` — Telegram commands, conversations, menus and Ollama chat.
- `academics.py` — subject catalog, dataset loading and Exam Rescue algorithm.
- `memory.py` — SQLite schema, profiles, memories and saved plans.
- `keyboards.py` — reusable inline keyboards.
- `config.py` — environment settings and validation.
- `data/subjects.json` — semester and branch-aware subject registry.
- `data/subjects/semester_3/` — five official-syllabus subject datasets.
- `tests/` — database, navigation and planning-algorithm tests.

## Upgrade safely

1. Stop Raven with `CTRL+C`.
2. Commit or copy your existing Raven folder as a backup.
3. Replace the Python, README and requirements files with the Sprint 2.3 files.
4. Replace the `data` folder with the Sprint 2.3 `data` folder.
5. Keep your existing `.env` and `raven_memory.db`.
6. In the active virtual environment, run:

```powershell
py -m pip install -r requirements.txt
py -m unittest discover -s tests -v
py bot.py
```

`init_db()` preserves existing messages, memories, student profiles and saved
plans while creating any missing tables automatically.

## Fresh installation

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

Copy `.env.example` to `.env`, insert the Telegram token and configured Ollama
model, and make sure Ollama is running before `py bot.py`. Never commit `.env`.

## Commands

- `/start` — begin onboarding or open Raven.
- `/setup` — create or update the student profile.
- `/profile` — view the current profile.
- `/menu` — open Raven's feature menu.
- `/lastplan` — retrieve the latest Exam Rescue plan.
- `/remember <text>` — save a long-term memory.
- `/memories` — list memories.
- `/forget <id>` — delete one memory.
- `/forgetall CONFIRM` — delete all memories.
- `/reset` — clear recent chat history only.
- `/cancel` — cancel onboarding or Exam Rescue.

## Data limitations and next step

The current datasets combine official AKTU syllabus topics with verified free
starter videos. They do not contain Gateway-app notes or private JSS papers.
The next Academic data sprint should collect public PYQs, extract questions,
map them to official topics and replace neutral planning weights with evidence-
based repeat and marks data.
