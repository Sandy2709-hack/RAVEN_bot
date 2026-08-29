import sqlite3
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
    with get_connection() as connection:
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

        connection.commit()


def save_message(chat_id: int, role: str, content: str) -> None:
    role = role.strip().lower()

    if role not in {"user", "assistant", "system"}:
        raise ValueError("role must be user, assistant, or system")

    with get_connection() as connection:
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

    with get_connection() as connection:
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
    with get_connection() as connection:
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

    with get_connection() as connection:
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

    with get_connection() as connection:
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
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM memories WHERE id = ? AND chat_id = ?",
            (memory_id, chat_id),
        )
        connection.commit()
        return cursor.rowcount > 0


def clear_memories(chat_id: int) -> int:
    with get_connection() as connection:
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

    with get_connection() as connection:
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
    with get_connection() as connection:
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
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM student_profiles WHERE chat_id = ?",
            (chat_id,),
        )
        connection.commit()
        return cursor.rowcount > 0
