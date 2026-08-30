import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "raven_memory.db"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def init_db() -> None:
    with closing(get_connection()) as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_chat_id
            ON messages(chat_id)
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                memory_key TEXT,
                content TEXT NOT NULL,
                importance INTEGER NOT NULL DEFAULT 5,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memories_chat_id
            ON memories(chat_id)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memories_key
            ON memories(chat_id, memory_key)
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS student_profiles (
                chat_id INTEGER PRIMARY KEY,
                telegram_user_id INTEGER NOT NULL,
                telegram_username TEXT,
                full_name TEXT NOT NULL,
                college TEXT NOT NULL,
                branch TEXT NOT NULL,
                academic_year INTEGER NOT NULL
                    CHECK (academic_year BETWEEN 1 AND 4),
                semester INTEGER NOT NULL
                    CHECK (semester BETWEEN 1 AND 8),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_profiles_college_branch
            ON student_profiles(college, branch)
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS exam_rescue_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                subject_code TEXT NOT NULL,
                days INTEGER NOT NULL,
                -- Retained internally for compatibility with Sprint 2 databases.
                -- Students are no longer asked to provide this value.
                hours_per_day REAL NOT NULL,
                target_score INTEGER NOT NULL,
                completed_units TEXT NOT NULL DEFAULT '[]',
                plan_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_rescue_plans_chat_subject
            ON exam_rescue_plans(chat_id, subject_code, created_at)
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS student_subject_progress (
                chat_id INTEGER NOT NULL,
                subject_code TEXT NOT NULL,
                preparation_level TEXT NOT NULL DEFAULT 'not_started'
                    CHECK (
                        preparation_level IN (
                            'not_started',
                            'basics_completed',
                            'mostly_prepared',
                            'revision_only'
                        )
                    ),
                completed_units TEXT NOT NULL DEFAULT '[]',
                latest_score REAL,
                latest_score_max REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (chat_id, subject_code)
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_subject_progress_chat
            ON student_subject_progress(chat_id, updated_at)
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance_settings (
                chat_id INTEGER PRIMARY KEY,
                section TEXT NOT NULL,
                batch_group TEXT NOT NULL,
                target_percentage REAL NOT NULL DEFAULT 75
                    CHECK (target_percentage >= 1 AND target_percentage < 100),
                reminder_time TEXT NOT NULL DEFAULT '20:00',
                semester_start TEXT NOT NULL,
                semester_end TEXT,
                cia_dates TEXT NOT NULL DEFAULT '[]',
                setup_complete INTEGER NOT NULL DEFAULT 0
                    CHECK (setup_complete IN (0, 1)),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance_baselines (
                chat_id INTEGER NOT NULL,
                subject_code TEXT NOT NULL,
                subject_name TEXT NOT NULL,
                short_name TEXT NOT NULL,
                attended INTEGER NOT NULL DEFAULT 0 CHECK (attended >= 0),
                absent INTEGER NOT NULL DEFAULT 0 CHECK (absent >= 0),
                estimated INTEGER NOT NULL DEFAULT 0
                    CHECK (estimated IN (0, 1)),
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                display_order INTEGER NOT NULL DEFAULT 999,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (chat_id, subject_code),
                FOREIGN KEY (chat_id)
                    REFERENCES attendance_settings(chat_id)
                    ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                subject_code TEXT NOT NULL,
                class_date TEXT NOT NULL,
                timetable_entry_id TEXT NOT NULL,
                period_label TEXT NOT NULL,
                class_count INTEGER NOT NULL DEFAULT 1 CHECK (class_count > 0),
                status TEXT NOT NULL
                    CHECK (
                        status IN (
                            'attended',
                            'absent',
                            'cancelled',
                            'planned_bunk'
                        )
                    ),
                reason TEXT,
                source TEXT NOT NULL DEFAULT 'daily_checklist',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (chat_id, class_date, timetable_entry_id),
                FOREIGN KEY (chat_id)
                    REFERENCES attendance_settings(chat_id)
                    ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_attendance_events_chat_date
            ON attendance_events(chat_id, class_date, updated_at)
            """
        )

        connection.commit()


def save_message(chat_id: int, role: str, content: str) -> None:
    role = role.strip().lower()

    if role not in {"user", "assistant", "system"}:
        raise ValueError("role must be user, assistant, or system")

    with closing(get_connection()) as connection:
        connection.execute(
            """
            INSERT INTO messages (chat_id, role, content)
            VALUES (?, ?, ?)
            """,
            (chat_id, role, content.strip()),
        )
        connection.commit()


def get_recent_messages(chat_id: int, limit: int = 20) -> list[dict[str, str]]:
    limit = max(1, min(100, int(limit)))

    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT role, content
            FROM messages
            WHERE chat_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (chat_id, limit),
        ).fetchall()

    rows.reverse()
    return [
        {"role": row["role"], "content": row["content"]}
        for row in rows
    ]


def clear_chat_history(chat_id: int) -> int:
    with closing(get_connection()) as connection:
        cursor = connection.execute(
            "DELETE FROM messages WHERE chat_id = ?",
            (chat_id,),
        )
        connection.commit()
        return cursor.rowcount


def save_memory(
    chat_id: int,
    content: str,
    category: str = "general",
    memory_key: str | None = None,
    importance: int = 5,
) -> tuple[int, str]:
    content = content.strip()

    if not content:
        raise ValueError("Memory content cannot be empty")

    category = category.strip() or "general"
    memory_key = memory_key.strip() if memory_key else None
    importance = max(1, min(10, int(importance)))

    with closing(get_connection()) as connection:
        cursor = connection.cursor()

        if memory_key:
            existing = cursor.execute(
                """
                SELECT id
                FROM memories
                WHERE chat_id = ? AND memory_key = ?
                LIMIT 1
                """,
                (chat_id, memory_key),
            ).fetchone()

            if existing:
                memory_id = existing["id"]
                cursor.execute(
                    """
                    UPDATE memories
                    SET category = ?,
                        content = ?,
                        importance = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND chat_id = ?
                    """,
                    (category, content, importance, memory_id, chat_id),
                )
                connection.commit()
                return memory_id, "updated"

        duplicate = cursor.execute(
            """
            SELECT id
            FROM memories
            WHERE chat_id = ? AND LOWER(content) = LOWER(?)
            LIMIT 1
            """,
            (chat_id, content),
        ).fetchone()

        if duplicate:
            return duplicate["id"], "exists"

        cursor.execute(
            """
            INSERT INTO memories (
                chat_id,
                category,
                memory_key,
                content,
                importance
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (chat_id, category, memory_key, content, importance),
        )
        memory_id = cursor.lastrowid
        connection.commit()
        return int(memory_id), "created"


def get_memories(chat_id: int, limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(200, int(limit)))

    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                category,
                memory_key,
                content,
                importance,
                created_at,
                updated_at
            FROM memories
            WHERE chat_id = ?
            ORDER BY importance DESC, updated_at DESC
            LIMIT ?
            """,
            (chat_id, limit),
        ).fetchall()

    return [
        {
            "id": row["id"],
            "category": row["category"],
            "key": row["memory_key"],
            "content": row["content"],
            "importance": row["importance"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def delete_memory(chat_id: int, memory_id: int) -> bool:
    with closing(get_connection()) as connection:
        cursor = connection.execute(
            "DELETE FROM memories WHERE id = ? AND chat_id = ?",
            (memory_id, chat_id),
        )
        connection.commit()
        return cursor.rowcount > 0


def clear_memories(chat_id: int) -> int:
    with closing(get_connection()) as connection:
        cursor = connection.execute(
            "DELETE FROM memories WHERE chat_id = ?",
            (chat_id,),
        )
        connection.commit()
        return cursor.rowcount


def save_student_profile(
    *,
    chat_id: int,
    telegram_user_id: int,
    telegram_username: str | None,
    full_name: str,
    college: str,
    branch: str,
    academic_year: int,
    semester: int,
) -> None:
    if academic_year not in range(1, 5):
        raise ValueError("Academic year must be between 1 and 4")

    if semester not in range(1, 9):
        raise ValueError("Semester must be between 1 and 8")

    with closing(get_connection()) as connection:
        connection.execute(
            """
            INSERT INTO student_profiles (
                chat_id,
                telegram_user_id,
                telegram_username,
                full_name,
                college,
                branch,
                academic_year,
                semester
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                telegram_user_id = excluded.telegram_user_id,
                telegram_username = excluded.telegram_username,
                full_name = excluded.full_name,
                college = excluded.college,
                branch = excluded.branch,
                academic_year = excluded.academic_year,
                semester = excluded.semester,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                chat_id,
                telegram_user_id,
                telegram_username,
                full_name.strip(),
                college.strip(),
                branch.strip().upper(),
                academic_year,
                semester,
            ),
        )
        connection.commit()


def get_student_profile(chat_id: int) -> dict[str, Any] | None:
    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT
                chat_id,
                telegram_user_id,
                telegram_username,
                full_name,
                college,
                branch,
                academic_year,
                semester,
                created_at,
                updated_at
            FROM student_profiles
            WHERE chat_id = ?
            """,
            (chat_id,),
        ).fetchone()

    return dict(row) if row else None


def delete_student_profile(chat_id: int) -> bool:
    with closing(get_connection()) as connection:
        cursor = connection.execute(
            "DELETE FROM student_profiles WHERE chat_id = ?",
            (chat_id,),
        )
        connection.commit()
        return cursor.rowcount > 0


def save_exam_rescue_plan(chat_id: int, plan: dict[str, Any]) -> int:
    required = {
        "subject_code",
        "days",
        "daily_minutes",
        "target_score",
        "completed_units",
    }

    if not required.issubset(plan):
        missing = ", ".join(sorted(required - set(plan)))
        raise ValueError(f"Exam Rescue plan is missing: {missing}")

    plan_json = json.dumps(plan, ensure_ascii=False)
    completed_json = json.dumps(plan["completed_units"])

    with closing(get_connection()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO exam_rescue_plans (
                chat_id,
                subject_code,
                days,
                hours_per_day,
                target_score,
                completed_units,
                plan_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                plan["subject_code"],
                plan["days"],
                plan["daily_minutes"] / 60,
                plan["target_score"],
                completed_json,
                plan_json,
            ),
        )
        plan_id = cursor.lastrowid
        connection.commit()
        return int(plan_id)


def get_latest_exam_rescue_plan(
    chat_id: int,
    subject_code: str | None = None,
) -> dict[str, Any] | None:
    with closing(get_connection()) as connection:
        if subject_code:
            row = connection.execute(
                """
                SELECT id, plan_json, created_at
                FROM exam_rescue_plans
                WHERE chat_id = ? AND subject_code = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (chat_id, subject_code.upper()),
            ).fetchone()
        else:
            row = connection.execute(
                """
                SELECT id, plan_json, created_at
                FROM exam_rescue_plans
                WHERE chat_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (chat_id,),
            ).fetchone()

    if not row:
        return None

    plan = json.loads(row["plan_json"])
    plan["plan_id"] = row["id"]
    plan["created_at"] = row["created_at"]
    return plan


PREPARATION_LEVELS = {
    "not_started",
    "basics_completed",
    "mostly_prepared",
    "revision_only",
}


def _normalise_completed_units(completed_units: set[int] | list[int]) -> list[int]:
    units = sorted({int(unit) for unit in completed_units})
    if any(unit not in range(1, 21) for unit in units):
        raise ValueError("completed_units must contain unit numbers from 1 to 20")
    return units


def save_subject_progress(
    *,
    chat_id: int,
    subject_code: str,
    preparation_level: str | None = None,
    completed_units: set[int] | list[int] | None = None,
    latest_score: float | None = None,
    latest_score_max: float | None = None,
) -> dict[str, Any]:
    subject_code = subject_code.strip().upper()
    if not subject_code:
        raise ValueError("subject_code cannot be empty")

    existing = get_subject_progress(chat_id, subject_code)
    level = preparation_level or (
        existing["preparation_level"] if existing else "not_started"
    )
    if level not in PREPARATION_LEVELS:
        valid = ", ".join(sorted(PREPARATION_LEVELS))
        raise ValueError(f"preparation_level must be one of: {valid}")

    if completed_units is None:
        units = existing["completed_units"] if existing else []
    else:
        units = _normalise_completed_units(completed_units)

    score = latest_score
    score_max = latest_score_max
    if latest_score is None and existing:
        score = existing["latest_score"]
        if latest_score_max is None:
            score_max = existing["latest_score_max"]

    if score is not None:
        score = float(score)
        if score < 0:
            raise ValueError("latest_score cannot be negative")

    if score_max is not None:
        score_max = float(score_max)
        if score_max <= 0:
            raise ValueError("latest_score_max must be positive")
        if score is None:
            raise ValueError("latest_score is required with latest_score_max")
        if score > score_max:
            raise ValueError("latest_score cannot exceed latest_score_max")

    with closing(get_connection()) as connection:
        connection.execute(
            """
            INSERT INTO student_subject_progress (
                chat_id,
                subject_code,
                preparation_level,
                completed_units,
                latest_score,
                latest_score_max
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id, subject_code) DO UPDATE SET
                preparation_level = excluded.preparation_level,
                completed_units = excluded.completed_units,
                latest_score = excluded.latest_score,
                latest_score_max = excluded.latest_score_max,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                chat_id,
                subject_code,
                level,
                json.dumps(units),
                score,
                score_max,
            ),
        )
        connection.commit()

    saved = get_subject_progress(chat_id, subject_code)
    if saved is None:
        raise RuntimeError("Subject progress was not saved")
    return saved


def get_subject_progress(
    chat_id: int,
    subject_code: str,
) -> dict[str, Any] | None:
    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT
                chat_id,
                subject_code,
                preparation_level,
                completed_units,
                latest_score,
                latest_score_max,
                created_at,
                updated_at
            FROM student_subject_progress
            WHERE chat_id = ? AND subject_code = ?
            """,
            (chat_id, subject_code.strip().upper()),
        ).fetchone()

    if not row:
        return None

    result = dict(row)
    try:
        result["completed_units"] = _normalise_completed_units(
            json.loads(result["completed_units"])
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        result["completed_units"] = []
    return result


def get_all_subject_progress(chat_id: int) -> list[dict[str, Any]]:
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT subject_code
            FROM student_subject_progress
            WHERE chat_id = ?
            ORDER BY subject_code
            """,
            (chat_id,),
        ).fetchall()

    return [
        progress
        for row in rows
        if (progress := get_subject_progress(chat_id, row["subject_code"])) is not None
    ]


# =========================================================
# ATTENDANCE SETTINGS AND BASELINES
# =========================================================

def save_attendance_settings(
    *,
    chat_id: int,
    section: str,
    batch_group: str,
    semester_start: str,
    semester_end: str | None = None,
    cia_dates: list[str] | None = None,
    target_percentage: float = 75.0,
    reminder_time: str = "20:00",
    setup_complete: bool = False,
) -> dict[str, Any]:
    section = section.strip().upper()
    batch_group = batch_group.strip().upper()
    target_percentage = float(target_percentage)
    if not section or not batch_group:
        raise ValueError("section and batch_group are required")
    if not 1 <= target_percentage < 100:
        raise ValueError("target_percentage must be between 1 and 99.99")

    try:
        hour_text, minute_text = reminder_time.split(":", maxsplit=1)
        hour, minute = int(hour_text), int(minute_text)
    except (ValueError, AttributeError):
        raise ValueError("reminder_time must use HH:MM") from None
    if hour not in range(24) or minute not in range(60):
        raise ValueError("reminder_time must be a valid 24-hour time")

    with closing(get_connection()) as connection:
        connection.execute(
            """
            INSERT INTO attendance_settings (
                chat_id,
                section,
                batch_group,
                target_percentage,
                reminder_time,
                semester_start,
                semester_end,
                cia_dates,
                setup_complete
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                section = excluded.section,
                batch_group = excluded.batch_group,
                target_percentage = excluded.target_percentage,
                reminder_time = excluded.reminder_time,
                semester_start = excluded.semester_start,
                semester_end = excluded.semester_end,
                cia_dates = excluded.cia_dates,
                setup_complete = excluded.setup_complete,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                chat_id,
                section,
                batch_group,
                target_percentage,
                reminder_time,
                semester_start,
                semester_end,
                json.dumps(sorted(set(cia_dates or []))),
                int(setup_complete),
            ),
        )
        connection.commit()

    settings = get_attendance_settings(chat_id)
    if settings is None:
        raise RuntimeError("Attendance settings were not saved")
    return settings


def get_attendance_settings(chat_id: int) -> dict[str, Any] | None:
    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM attendance_settings
            WHERE chat_id = ?
            """,
            (chat_id,),
        ).fetchone()

    if not row:
        return None
    result = dict(row)
    try:
        result["cia_dates"] = json.loads(result["cia_dates"])
    except (TypeError, json.JSONDecodeError):
        result["cia_dates"] = []
    result["setup_complete"] = bool(result["setup_complete"])
    return result


def get_all_attendance_settings(*, complete_only: bool = True) -> list[dict[str, Any]]:
    query = "SELECT chat_id FROM attendance_settings"
    if complete_only:
        query += " WHERE setup_complete = 1"
    query += " ORDER BY chat_id"

    with closing(get_connection()) as connection:
        rows = connection.execute(query).fetchall()
    return [
        settings
        for row in rows
        if (settings := get_attendance_settings(row["chat_id"])) is not None
    ]


def deactivate_attendance_baselines(chat_id: int) -> None:
    with closing(get_connection()) as connection:
        connection.execute(
            """
            UPDATE attendance_baselines
            SET active = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE chat_id = ?
            """,
            (chat_id,),
        )
        connection.commit()


def save_attendance_baseline(
    *,
    chat_id: int,
    subject_code: str,
    subject_name: str,
    short_name: str,
    attended: int,
    conducted: int,
    estimated: bool = False,
    active: bool = True,
    display_order: int = 999,
) -> dict[str, Any]:
    subject_code = subject_code.strip().upper()
    attended = int(attended)
    conducted = int(conducted)
    if not subject_code:
        raise ValueError("subject_code is required")
    if attended < 0 or conducted < 0 or attended > conducted:
        raise ValueError("attended must be between 0 and conducted")
    absent = conducted - attended

    with closing(get_connection()) as connection:
        connection.execute(
            """
            INSERT INTO attendance_baselines (
                chat_id,
                subject_code,
                subject_name,
                short_name,
                attended,
                absent,
                estimated,
                active,
                display_order
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id, subject_code) DO UPDATE SET
                subject_name = excluded.subject_name,
                short_name = excluded.short_name,
                attended = excluded.attended,
                absent = excluded.absent,
                estimated = excluded.estimated,
                active = excluded.active,
                display_order = excluded.display_order,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                chat_id,
                subject_code,
                subject_name.strip(),
                short_name.strip(),
                attended,
                absent,
                int(estimated),
                int(active),
                int(display_order),
            ),
        )
        connection.commit()

    baseline = get_attendance_baseline(chat_id, subject_code)
    if baseline is None:
        raise RuntimeError("Attendance baseline was not saved")
    return baseline


def get_attendance_baseline(
    chat_id: int,
    subject_code: str,
) -> dict[str, Any] | None:
    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM attendance_baselines
            WHERE chat_id = ? AND subject_code = ?
            """,
            (chat_id, subject_code.strip().upper()),
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    result["estimated"] = bool(result["estimated"])
    result["active"] = bool(result["active"])
    return result


def get_attendance_baselines(
    chat_id: int,
    *,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    query = "SELECT subject_code FROM attendance_baselines WHERE chat_id = ?"
    if active_only:
        query += " AND active = 1"
    query += " ORDER BY display_order, subject_code"

    with closing(get_connection()) as connection:
        rows = connection.execute(query, (chat_id,)).fetchall()
    return [
        baseline
        for row in rows
        if (
            baseline := get_attendance_baseline(chat_id, row["subject_code"])
        ) is not None
    ]


# =========================================================
# ATTENDANCE EVENTS
# =========================================================

ATTENDANCE_EVENT_STATUSES = {
    "attended",
    "absent",
    "cancelled",
    "planned_bunk",
}


def save_attendance_event(
    *,
    chat_id: int,
    subject_code: str,
    class_date: str,
    timetable_entry_id: str,
    period_label: str,
    class_count: int,
    status: str,
    reason: str | None = None,
    source: str = "daily_checklist",
) -> dict[str, Any]:
    subject_code = subject_code.strip().upper()
    status = status.strip().lower()
    class_count = int(class_count)
    if status not in ATTENDANCE_EVENT_STATUSES:
        raise ValueError("Invalid attendance event status")
    if class_count <= 0:
        raise ValueError("class_count must be positive")

    with closing(get_connection()) as connection:
        connection.execute(
            """
            INSERT INTO attendance_events (
                chat_id,
                subject_code,
                class_date,
                timetable_entry_id,
                period_label,
                class_count,
                status,
                reason,
                source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id, class_date, timetable_entry_id) DO UPDATE SET
                subject_code = excluded.subject_code,
                period_label = excluded.period_label,
                class_count = excluded.class_count,
                status = excluded.status,
                reason = excluded.reason,
                source = excluded.source,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                chat_id,
                subject_code,
                class_date,
                timetable_entry_id,
                period_label,
                class_count,
                status,
                reason.strip() if reason else None,
                source.strip() or "daily_checklist",
            ),
        )
        connection.commit()

    event = get_attendance_event_for_entry(chat_id, class_date, timetable_entry_id)
    if event is None:
        raise RuntimeError("Attendance event was not saved")
    return event


def get_attendance_event(event_id: int, chat_id: int) -> dict[str, Any] | None:
    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM attendance_events
            WHERE id = ? AND chat_id = ?
            """,
            (int(event_id), chat_id),
        ).fetchone()
    return dict(row) if row else None


def get_attendance_event_for_entry(
    chat_id: int,
    class_date: str,
    timetable_entry_id: str,
) -> dict[str, Any] | None:
    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM attendance_events
            WHERE chat_id = ?
              AND class_date = ?
              AND timetable_entry_id = ?
            """,
            (chat_id, class_date, timetable_entry_id),
        ).fetchone()
    return dict(row) if row else None


def get_attendance_events_for_date(
    chat_id: int,
    class_date: str,
) -> list[dict[str, Any]]:
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM attendance_events
            WHERE chat_id = ? AND class_date = ?
            ORDER BY id
            """,
            (chat_id, class_date),
        ).fetchall()
    return [dict(row) for row in rows]


def update_attendance_event_status(
    *,
    chat_id: int,
    event_id: int,
    status: str,
    reason: str | None = None,
) -> dict[str, Any] | None:
    status = status.strip().lower()
    if status not in ATTENDANCE_EVENT_STATUSES:
        raise ValueError("Invalid attendance event status")

    with closing(get_connection()) as connection:
        cursor = connection.execute(
            """
            UPDATE attendance_events
            SET status = ?,
                reason = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND chat_id = ?
            """,
            (status, reason.strip() if reason else None, int(event_id), chat_id),
        )
        connection.commit()
    return get_attendance_event(event_id, chat_id) if cursor.rowcount else None


def delete_attendance_event_for_entry(
    chat_id: int,
    class_date: str,
    timetable_entry_id: str,
) -> bool:
    with closing(get_connection()) as connection:
        cursor = connection.execute(
            """
            DELETE FROM attendance_events
            WHERE chat_id = ?
              AND class_date = ?
              AND timetable_entry_id = ?
            """,
            (chat_id, class_date, timetable_entry_id),
        )
        connection.commit()
        return cursor.rowcount > 0


def clear_attendance_events(chat_id: int) -> int:
    with closing(get_connection()) as connection:
        cursor = connection.execute(
            "DELETE FROM attendance_events WHERE chat_id = ?",
            (chat_id,),
        )
        connection.commit()
        return cursor.rowcount


def undo_last_attendance_event(chat_id: int) -> dict[str, Any] | None:
    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM attendance_events
            WHERE chat_id = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (chat_id,),
        ).fetchone()
        if not row:
            return None
        connection.execute(
            "DELETE FROM attendance_events WHERE id = ? AND chat_id = ?",
            (row["id"], chat_id),
        )
        connection.commit()
    return dict(row)


def get_recent_attendance_events(
    chat_id: int,
    limit: int = 10,
) -> list[dict[str, Any]]:
    limit = max(1, min(100, int(limit)))
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM attendance_events
            WHERE chat_id = ?
            ORDER BY class_date DESC, updated_at DESC, id DESC
            LIMIT ?
            """,
            (chat_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_attendance_totals(chat_id: int) -> list[dict[str, Any]]:
    baselines = get_attendance_baselines(chat_id, active_only=True)
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT
                subject_code,
                SUM(CASE WHEN status = 'attended' THEN class_count ELSE 0 END)
                    AS attended_delta,
                SUM(CASE WHEN status = 'absent' THEN class_count ELSE 0 END)
                    AS absent_delta
            FROM attendance_events
            WHERE chat_id = ?
            GROUP BY subject_code
            """,
            (chat_id,),
        ).fetchall()
    deltas = {row["subject_code"]: dict(row) for row in rows}

    totals = []
    for baseline in baselines:
        delta = deltas.get(baseline["subject_code"], {})
        totals.append(
            {
                **baseline,
                "attended": baseline["attended"]
                + int(delta.get("attended_delta") or 0),
                "absent": baseline["absent"]
                + int(delta.get("absent_delta") or 0),
            }
        )
    return totals
