import unittest

from academics import (
    build_exam_rescue_plan,
    format_coa_resources,
    format_coa_syllabus,
    format_exam_rescue_plan,
    load_coa_subject,
)


class AcademicsTests(unittest.TestCase):
    def test_official_coa_dataset_has_five_units(self) -> None:
        subject = load_coa_subject()

        self.assertEqual(subject["subject_code"], "BCS302")
        self.assertEqual(len(subject["units"]), 5)
        self.assertTrue(subject["syllabus_source"].startswith("https://"))

        for expected_number, unit in enumerate(subject["units"], start=1):
            self.assertEqual(unit["number"], expected_number)
            self.assertTrue(unit["topics"])
            self.assertTrue(unit["resources"][0]["url"].startswith("https://"))

    def test_plan_respects_total_available_time(self) -> None:
        plan = build_exam_rescue_plan(
            days=2,
            hours_per_day=2,
            completed_units=set(),
            target_score=60,
        )

        scheduled = sum(day["allocated_minutes"] for day in plan["days_plan"])
        self.assertEqual(plan["total_minutes"], 240)
        self.assertEqual(scheduled, 240)
        self.assertEqual(len(plan["days_plan"]), 2)

    def test_completed_unit_receives_less_time_than_unfinished_unit(self) -> None:
        plan = build_exam_rescue_plan(
            days=5,
            hours_per_day=2,
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
                days=0,
                hours_per_day=2,
                completed_units=set(),
                target_score=60,
            )

    def test_tiny_time_budget_avoids_three_minute_unit_blocks(self) -> None:
        plan = build_exam_rescue_plan(
            days=1,
            hours_per_day=0.5,
            completed_units=set(),
            target_score=40,
        )

        unit_items = [
            item
            for day in plan["days_plan"]
            for item in day["items"]
            if item.get("unit")
        ]

        self.assertEqual(len(unit_items), 1)
        self.assertGreaterEqual(unit_items[0]["minutes"], 15)
        self.assertEqual(len(plan["omitted_units"]), 4)

        with self.assertRaises(ValueError):
            build_exam_rescue_plan(
                days=2,
                hours_per_day=20,
                completed_units=set(),
                target_score=60,
            )

    def test_user_facing_text_contains_sources_and_status(self) -> None:
        plan = build_exam_rescue_plan(
            days=1,
            hours_per_day=2,
            completed_units={1},
            target_score=50,
        )

        plan_text = format_exam_rescue_plan(plan)
        syllabus_text = format_coa_syllabus()
        resources_text = format_coa_resources()

        self.assertIn("not yet PYQ-verified", plan_text)
        self.assertIn("Official syllabus", plan_text)
        self.assertIn("BCS302", syllabus_text)
        self.assertIn("Gateway Classes", resources_text)


if __name__ == "__main__":
    unittest.main()
