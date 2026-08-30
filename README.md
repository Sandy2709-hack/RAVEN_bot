# Raven Sprint 2.5 — Attendance Intelligence

Sprint 2.5 keeps the verified Academic Context Bridge from Sprint 2.4.1 and adds
deterministic attendance tracking, a verified JSS Semester 3 timetable, daily
checklists, safe-bunk calculations and the `/bunk` workflow.

This sprint does not add Semester Strategy navigation or PYQ rankings.

## Attendance Intelligence

The bundled timetable was transcribed and visually verified from the JSS
tentative odd-semester timetable effective 17 August 2026. It contains CSE1,
CSE2 and CSE3, their rooms, batch-specific laboratory blocks, Monday-Saturday
classes and the Asia/Kolkata timezone.

`/attendance` starts setup on first use. Raven asks for:

- section and lab batch;
- semester end and CIA dates, with `skip` supported when not announced;
- the current `attended/conducted` baseline for every timetable subject;
- `~14/18` for an estimated baseline, or `skip` for an unselected subject.

After setup, `/attendance` shows percentages, safety status, classes that may be
missed while staying at 75%, and consecutive classes needed to recover to 75%.
The 20:00 IST daily checklist is generated from the user's exact section and
batch. A class cycles through attended, absent, cancelled and unresolved states.
Cancelled classes and unresolved planned bunks do not affect the percentage.

Laboratory blocks spanning two timetable periods count as two attendance units.
Mentoring is present in the verified timetable but excluded from subject
attendance calculations.

`/bunk COA` finds today's COA class without asking for a date or weekday. Raven
records a pending outcome, then allows the student to confirm that the class was
cancelled, attended or marked absent. A successful mass bunk only leaves the
attendance denominator unchanged when the class was not held or attendance was
not marked.

## Hotfix in 2.4.1

- catalog-wide subject recognition now works even when an older student profile
  does not match a branch alias;
- a reply such as `COA, I mean` completes the pending resource or syllabus
  request instead of falling through to Ollama;
- unresolved academic requests remain deterministic and cannot ask Ollama to
  invent unit topics or links;
- subject-only corrections receive a safe acknowledgement;
- every stored YouTube video now includes a channel/title search fallback if a
  direct video is removed or regionally unavailable;
- additional CSE branch spellings are recognised.

## Available Semester 3 subjects

| Code | Subject | Credits |
| --- | --- | ---: |
| `BCS301` | Data Structure | 4 |
| `BCS302` | Computer Organization and Architecture (COA) | 4 |
| `BAS301` | Technical Communication | 3 |
| `BCC301` | Cyber Security | 2 |
| `BCS303` | Discrete Structures and Theory of Logic (DSTL) | 3 |

Credits are stored as JSON integers and validated whenever the catalog loads.
They are informational in Sprint 2.4 and are not yet used to rank subjects.

## Academic Context Bridge

Normal chat now recognises subject names, codes and common aliases. Examples:

```text
Give me the resources of Unit 4 of COA
Show DS Unit 2 syllabus
What topics are in Cyber Security Unit 3?
Explain cache memory in COA
How many credits does DSTL carry?
Which subjects have 4 credits?
```

Resource, syllabus and credit requests are answered directly from the local
catalog without calling Ollama. Explanation requests inject a small trusted
context block containing only the relevant subject/unit, saved preparation and
verified links. Short follow-ups such as `What about Unit 5 resources?` reuse
the last academic subject from the current Telegram session.

Stored YouTube links and resilient search fallbacks can be shared with the
student, but Raven does not watch
or understand the video itself. Transcript indexing is a separate future
feature.

## Preparation tracking

Raven stores preparation independently for every Telegram chat and subject:

- preparation level;
- completed units;
- optional latest score and maximum score;
- created and updated timestamps.

Supported preparation levels are `not_started`, `basics_completed`,
`mostly_prepared` and `revision_only`.

Students can update progress naturally:

```text
I completed COA Units 1 and 2
I haven't completed COA Unit 2
I scored 18/30 in COA
My DSTL preparation is mostly prepared
```

Use `/progress` for every current subject or `/progress COA` for one subject.
Exam Rescue loads saved completed units into its selector and saves the final
selection after creating a plan.

## Data safety

`init_db()` creates the preparation and attendance tables automatically.
Existing messages, long-term memories, profiles and Exam Rescue plans are
preserved. Progress and attendance are isolated by Telegram `chat_id`.

The attendance ledger keeps baseline totals separately from reversible daily
events. Re-running setup warns before replacing the baseline and clearing old
daily events, preventing double-counting. SQLite connections are explicitly
closed for Windows compatibility.

## Project files

- `bot.py` — Telegram commands, conversations, routing integration and Ollama.
- `academic_router.py` — deterministic academic intent and subject detection.
- `academics.py` — validated catalog, formatters and Exam Rescue algorithm.
- `memory.py` — SQLite memory, profiles, plans and preparation progress.
- `keyboards.py` — Telegram inline keyboards with subject credits.
- `attendance.py` — timetable lookup, date handling and attendance mathematics.
- `attendance_handlers.py` — setup, checklist, reminders and `/bunk` handlers.
- `data/subjects.json` — semester catalog and numeric credit values.
- `data/subjects/semester_3/` — official syllabus and starter resources.
- `data/timetables/jss/cse_semester_3.json` — directly accessible JSS timetable.
- `tests/` — routing, academics, keyboard and database tests.

## Safe upgrade from Sprint 2.4.1

1. Stop Raven with `CTRL+C`.
2. Commit or copy the existing project as a backup.
3. Replace the Sprint 2.4.1 Python files, tests, README, requirements and `data`
   folder with the Sprint 2.5 versions.
4. Keep the existing `.env` and `raven_memory.db`.
5. In the active virtual environment, run:

```powershell
py -m pip install -r requirements.txt
py -m unittest discover -s tests -v
py bot.py
```

The first start safely creates the new attendance tables. The JobQueue extra in
`requirements.txt` is required for the 20:00 IST reminder.

## Commands

- `/start` — begin onboarding or open Raven.
- `/setup` — create or update the student profile.
- `/profile` — view the student profile.
- `/menu` — open Raven's feature menu.
- `/progress [subject]` — view saved preparation.
- `/attendance [setup]` — set up attendance or open its dashboard.
- `/bunk <subject>` — plan and resolve today's subject bunk.
- `/lastplan` — retrieve the latest Exam Rescue plan.
- `/remember <text>` — save a long-term memory.
- `/memories` — list memories.
- `/forget <id>` — delete one memory.
- `/forgetall CONFIRM` — delete all memories.
- `/reset` — clear recent chat history only.
- `/cancel` — cancel onboarding, Exam Rescue or Attendance setup.

## Current limitations

- Syllabus and resource mappings are not yet ranked by verified PYQ frequency.
- Raven cannot read video content from a URL without a transcript collector.
- Credits do not yet drive a multi-subject semester strategy.
- The Academic catalog currently covers CSE and allied branches, Semester 3.
- Attendance timetable data currently covers JSS CSE1, CSE2 and CSE3 only.
- CIA and semester-end dates are user supplied until a verified calendar exists.
- Scheduled reminders run only while the bot process is online. Pending data is
  retained when the PC is off.

The planned next data sprint is PYQ Intelligence: collect public question
papers, extract questions, map them to official topics and calculate transparent
importance and confidence scores.
