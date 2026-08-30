import unittest
from datetime import date

from attendance import (
    available_batch_groups,
    available_sections,
    calculate_attendance,
    list_attendance_subjects,
    load_matching_timetable,
    match_subject,
    parse_cia_dates,
    schedule_for_date,
)


PROFILE = {
    "college": "JSS Academy of Technical Education, Noida",
    "branch": "CSE",
    "semester": 3,
}


class TimetableTests(unittest.TestCase):
    def setUp(self) -> None:
        self.timetable = load_matching_timetable(PROFILE)

    def test_jss_cse_timetable_matches_profile_and_lists_sections(self) -> None:
        self.assertIsNotNone(self.timetable)
        self.assertEqual(available_sections(self.timetable), ["CSE1", "CSE2", "CSE3"])
        self.assertEqual(
            available_batch_groups(self.timetable, "CSE3"),
            ["C1", "C2"],
        )

    def test_cse3_tuesday_lab_depends_on_batch(self) -> None:
        class_date = date(2026, 8, 18)  # Tuesday
        c1 = schedule_for_date(self.timetable, "CSE3", "C1", class_date)
        c2 = schedule_for_date(self.timetable, "CSE3", "C2", class_date)

        c1_codes = [entry["subject_code"] for entry in c1]
        c2_codes = [entry["subject_code"] for entry in c2]
        self.assertIn("BCS352", c1_codes)
        self.assertNotIn("BCS351", c1_codes)
        self.assertIn("BCS351", c2_codes)
        self.assertNotIn("BCS352", c2_codes)

        c1_lab = next(entry for entry in c1 if entry["subject_code"] == "BCS352")
        self.assertEqual(c1_lab["period_label"], "P3-P4")
        self.assertEqual(c1_lab["class_count"], 2)

    def test_non_attendance_mentoring_is_not_in_daily_checklist(self) -> None:
        monday = schedule_for_date(
            self.timetable,
            "CSE3",
            "C1",
            date(2026, 8, 17),
        )
        self.assertNotIn("MENTORING", [entry["subject_code"] for entry in monday])

    def test_subject_aliases_match_bunk_commands(self) -> None:
        subjects = list_attendance_subjects(self.timetable, "CSE3", "C1")
        self.assertEqual(match_subject("COA", subjects)["subject_code"], "BCS302")
        self.assertEqual(match_subject("DS Lab", subjects)["subject_code"], "BCS351")
        self.assertIsNone(match_subject("unknown subject", subjects))


class AttendanceCalculationTests(unittest.TestCase):
    def test_percentage_safe_bunks_and_recovery_are_deterministic(self) -> None:
        safe = calculate_attendance(14, 4, target_percentage=75)
        self.assertAlmostEqual(safe["percentage"], 77.777777, places=5)
        self.assertEqual(safe["safe_misses"], 0)
        self.assertEqual(safe["required_attends"], 0)

        danger = calculate_attendance(12, 6, target_percentage=75)
        self.assertAlmostEqual(danger["percentage"], 66.666666, places=5)
        self.assertEqual(danger["required_attends"], 6)
        self.assertEqual(danger["level"], "danger")

    def test_cia_dates_accept_indian_and_iso_formats(self) -> None:
        parsed = parse_cia_dates("15-09-2026, 2026-11-20")
        self.assertEqual(parsed, [date(2026, 9, 15), date(2026, 11, 20)])


if __name__ == "__main__":
    unittest.main()
