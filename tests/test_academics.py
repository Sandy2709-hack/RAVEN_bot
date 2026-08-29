import unittest

from academics import (
    build_exam_rescue_plan,
    format_coa_resources,
    format_coa_syllabus,
    format_exam_rescue_plan,
    format_subject_resources,
    format_subject_syllabus,
    list_subjects,
    load_coa_subject,
    load_subject,
)


class AcademicsTests(unittest.TestCase):
    def test_semester_catalog_contains_active_and_planned_subjects(self) -> None:
        subjects = list_subjects("CSE", 3, feature="exam_rescue")

        self.assertEqual(
            [subject["subject_code"] for subject in subjects],
            ["BCS302", "BCS301", "BCS303"],
        )
        self.assertEqual(subjects[0]["status"], "available")
        self.assertEqual(subjects[1]["status"], "planned")
        self.assertEqual(list_subjects("CSE", 4), [])

    def test_generic_subject_loader_rejects_planned_subjects(self) -> None:
        subject = load_subject("bcs302")
        self.assertEqual(subject["short_name"], "COA")

        with self.assertRaises(ValueError):
            load_subject("BCS301")

    def test_official_coa_dataset_has_five_units(self) -> None:
        subject = load_coa_subject()

        self.assertEqual(subject["subject_code"], "BCS302")
        self.assertEqual(len(subject["units"]), 5)
        self.assertTrue(subject["syllabus_source"].startswith("https://"))

        for expected_number, unit in enumerate(subject["units"], start=1):
            self.assertEqual(unit["number"], expected_number)
            self.assertTrue(unit["topics"])
            self.assertTrue(unit["resources"][0]["url"].startswith("https://"))

    def test_plan_respects_automatic_time_budget(self) -> None:
        plan = build_exam_rescue_plan(
            subject_code="BCS302",
            days=2,
            completed_units=set(),
            target_score=60,
        )

        scheduled = sum(day["allocated_minutes"] for day in plan["days_plan"])
        self.assertEqual(plan["daily_minutes"], 270)
        self.assertEqual(plan["total_minutes"], 540)
        self.assertEqual(scheduled, 540)
        self.assertEqual(len(plan["days_plan"]), 2)
        self.assertNotIn("hours_per_day", plan)

    def test_completed_unit_receives_less_time_than_unfinished_unit(self) -> None:
        plan = build_exam_rescue_plan(
            subject_code="BCS302",
            days=5,
            completed_units={4},
            target_score=60,
        )

        minutes_by_unit = {unit: 0 for unit in range(1, 6)}
        for day in plan["days_plan"]:
            for item in day["items"]:
                if item.get("unit"):
                    minutes_by_unit[item["unit"]] += item["minutes"]

        self.assertLess(minutes_by_unit[4], minutes_by_unit[2])

    def test_invalid_plan_inputs_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_exam_rescue_plan(
                subject_code="BCS302",
                days=0,
                completed_units=set(),
                target_score=60,
            )

        with self.assertRaises(ValueError):
            build_exam_rescue_plan(
                subject_code="BCS302",
                days=2,
                completed_units=set(),
                target_score=80,
            )

    def test_raven_sets_pace_from_days_and_target(self) -> None:
        urgent = build_exam_rescue_plan(
            subject_code="BCS302",
            days=1,
            completed_units=set(),
            target_score=70,
        )
        comfortable = build_exam_rescue_plan(
            subject_code="BCS302",
            days=20,
            completed_units=set(),
            target_score=40,
        )

        self.assertEqual(urgent["pace_label"], "Last-day rescue")
        self.assertEqual(comfortable["pace_label"], "Comfortable preparation")
        self.assertGreater(urgent["daily_minutes"], comfortable["daily_minutes"])

        with self.assertRaises(ValueError):
            build_exam_rescue_plan(
                subject_code="BCS302",
                days=31,
                completed_units=set(),
                target_score=60,
            )

    def test_user_facing_text_contains_sources_and_status(self) -> None:
        plan = build_exam_rescue_plan(
            subject_code="BCS302",
            days=1,
            completed_units={1},
            target_score=50,
        )

        plan_text = format_exam_rescue_plan(plan)
        syllabus_text = format_coa_syllabus()
        resources_text = format_coa_resources()

        self.assertIn("not yet PYQ-verified", plan_text)
        self.assertIn("Official syllabus", plan_text)
        self.assertIn("Raven pace: Last-day rescue", plan_text)
        self.assertNotIn("Daily study time", plan_text)
        self.assertIn("BCS302", syllabus_text)
        self.assertIn("Gateway Classes", resources_text)

        self.assertEqual(syllabus_text, format_subject_syllabus("BCS302"))
        self.assertEqual(resources_text, format_subject_resources("BCS302"))


if __name__ == "__main__":
    unittest.main()
