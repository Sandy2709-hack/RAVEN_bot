import tempfile
import unittest
from pathlib import Path

import memory


class MemoryDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        memory.DATABASE_PATH = Path(self.temp_dir.name) / "test_raven.db"
        memory.init_db()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_recent_messages_are_returned_in_conversation_order(self) -> None:
        memory.save_message(27, "user", "Hello")
        memory.save_message(27, "assistant", "Hi")

        self.assertEqual(
            memory.get_recent_messages(27),
            [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
            ],
        )

    def test_keyed_memory_is_updated_instead_of_duplicated(self) -> None:
        first_id, first_status = memory.save_memory(
            27,
            "Semester 2",
            category="academic",
            memory_key="semester",
        )
        second_id, second_status = memory.save_memory(
            27,
            "Semester 3",
            category="academic",
            memory_key="semester",
        )

        self.assertEqual(first_status, "created")
        self.assertEqual(second_status, "updated")
        self.assertEqual(first_id, second_id)
        self.assertEqual(memory.get_memories(27)[0]["content"], "Semester 3")

    def test_student_profile_can_be_created_and_updated(self) -> None:
        memory.save_student_profile(
            chat_id=27,
            telegram_user_id=27,
            telegram_username="sandy",
            full_name="Vishesh Singh",
            college="JSS Academy of Technical Education, Noida",
            branch="cse",
            academic_year=2,
            semester=3,
        )

        profile = memory.get_student_profile(27)
        self.assertEqual(profile["branch"], "CSE")
        self.assertEqual(profile["semester"], 3)

        memory.save_student_profile(
            chat_id=27,
            telegram_user_id=27,
            telegram_username="sandy",
            full_name="Vishesh Singh",
            college="JSS Academy of Technical Education, Noida",
            branch="CSE",
            academic_year=2,
            semester=4,
        )

        updated = memory.get_student_profile(27)
        self.assertEqual(updated["semester"], 4)


if __name__ == "__main__":
    unittest.main()
