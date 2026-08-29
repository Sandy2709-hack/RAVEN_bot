# Raven Sprint 2.4.1 — Academic Context Hotfix

Sprint 2.4.1 connects Raven's normal chat to its verified Academic catalog. Exact
resource, syllabus, credit and progress requests are handled deterministically;
Ollama receives only the relevant subject or unit context when an explanation
is needed.

This sprint does not add Semester Strategy navigation or PYQ rankings.

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

`init_db()` creates the `student_subject_progress` table automatically. Existing
messages, long-term memories, profiles and Exam Rescue plans are preserved.
Progress is isolated by both Telegram `chat_id` and subject code.

## Project files

- `bot.py` — Telegram commands, conversations, routing integration and Ollama.
- `academic_router.py` — deterministic academic intent and subject detection.
- `academics.py` — validated catalog, formatters and Exam Rescue algorithm.
- `memory.py` — SQLite memory, profiles, plans and preparation progress.
- `keyboards.py` — Telegram inline keyboards with subject credits.
- `data/subjects.json` — semester catalog and numeric credit values.
- `data/subjects/semester_3/` — official syllabus and starter resources.
- `tests/` — routing, academics, keyboard and database tests.

## Safe upgrade from Sprint 2.3

1. Stop Raven with `CTRL+C`.
2. Commit or copy the existing project as a backup.
3. Replace the Sprint 2.3 Python files, tests, README and `data` folder with the
   Sprint 2.4 versions.
4. Keep the existing `.env` and `raven_memory.db`.
5. In the active virtual environment, run:

```powershell
py -m pip install -r requirements.txt
py -m unittest discover -s tests -v
py bot.py
```

The first start safely creates the new progress table.

## Commands

- `/start` — begin onboarding or open Raven.
- `/setup` — create or update the student profile.
- `/profile` — view the student profile.
- `/menu` — open Raven's feature menu.
- `/progress [subject]` — view saved preparation.
- `/lastplan` — retrieve the latest Exam Rescue plan.
- `/remember <text>` — save a long-term memory.
- `/memories` — list memories.
- `/forget <id>` — delete one memory.
- `/forgetall CONFIRM` — delete all memories.
- `/reset` — clear recent chat history only.
- `/cancel` — cancel onboarding or Exam Rescue.

## Current limitations

- Syllabus and resource mappings are not yet ranked by verified PYQ frequency.
- Raven cannot read video content from a URL without a transcript collector.
- Credits do not yet drive a multi-subject semester strategy.
- The Academic catalog currently covers CSE and allied branches, Semester 3.

The planned next data sprint is PYQ Intelligence: collect public question
papers, extract questions, map them to official topics and calculate transparent
importance and confidence scores.
