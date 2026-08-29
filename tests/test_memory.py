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

    def test_exam_rescue_plan_is_saved_and_retrieved(self) -> None:
        plan = {
            "subject_code": "BCS302",
            "days": 2,
            "daily_minutes": 270,
            "pace_label": "Emergency sprint",
            "target_score": 60,
            "completed_units": [1],
            "days_plan": [],
        }

        plan_id = memory.save_exam_rescue_plan(27, plan)
        saved = memory.get_latest_exam_rescue_plan(27)

        self.assertGreater(plan_id, 0)
        self.assertEqual(saved["plan_id"], plan_id)
        self.assertEqual(saved["target_score"], 60)
        self.assertEqual(saved["completed_units"], [1])
        self.assertEqual(saved["daily_minutes"], 270)

        second_plan = dict(plan)
        second_plan["subject_code"] = "BCS301"
        second_plan["target_score"] = 50
        second_id = memory.save_exam_rescue_plan(27, second_plan)

        latest = memory.get_latest_exam_rescue_plan(27)
        latest_coa = memory.get_latest_exam_rescue_plan(27, "bcs302")
        self.assertEqual(latest["plan_id"], second_id)
        self.assertEqual(latest["subject_code"], "BCS301")
        self.assertEqual(latest_coa["plan_id"], plan_id)

    def test_subject_progress_is_created_updated_and_isolated(self) -> None:
        created = memory.save_subject_progress(
            chat_id=27,
            subject_code="bcs302",
            preparation_level="basics_completed",
            completed_units={2, 1},
            latest_score=18,
            latest_score_max=30,
        )

        self.assertEqual(created["subject_code"], "BCS302")
        self.assertEqual(created["completed_units"], [1, 2])
        self.assertEqual(created["latest_score"], 18)
        self.assertEqual(created["latest_score_max"], 30)

        updated = memory.save_subject_progress(
            chat_id=27,
            subject_code="BCS302",
            preparation_level="mostly_prepared",
            completed_units=[1, 2, 3, 4],
        )
        memory.save_subject_progress(
            chat_id=99,
            subject_code="BCS302",
            completed_units=[5],
        )

        self.assertEqual(updated["preparation_level"], "mostly_prepared")
        self.assertEqual(updated["completed_units"], [1, 2, 3, 4])
        self.assertEqual(updated["latest_score"], 18)
        self.assertEqual(
            memory.get_subject_progress(99, "BCS302")["completed_units"],
            [5],
        )
        self.assertEqual(len(memory.get_all_subject_progress(27)), 1)

    def test_invalid_subject_progress_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            memory.save_subject_progress(
                chat_id=27,
                subject_code="BCS302",
                preparation_level="perfect",
            )

        with self.assertRaises(ValueError):
            memory.save_subject_progress(
                chat_id=27,
                subject_code="BCS302",
                completed_units=[21],
            )

        with self.assertRaises(ValueError):
            memory.save_subject_progress(
                chat_id=27,
                subject_code="BCS302",
                latest_score=31,
                latest_score_max=30,
            )


if __name__ == "__main__":
    unittest.main()
