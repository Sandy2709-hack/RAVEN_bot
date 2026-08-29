import unittest

from academic_router import (
    build_academic_context,
    format_progress_summary,
    looks_like_academic_followup,
    route_academic_message,
)
from academics import list_subjects


class AcademicRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.subjects = list_subjects("CSE", 3)

    def test_unit_resource_request_is_answered_from_catalog(self) -> None:
        route = route_academic_message(
            "give me the resources of unit 4 of COA",
            self.subjects,
        )

        self.assertEqual(route.kind, "direct")
        self.assertEqual(route.intent, "resources")
        self.assertEqual(route.subject_code, "BCS302")
        self.assertEqual(route.unit_numbers, (4,))
        self.assertIn("Gateway Classes", route.response)
        self.assertIn("https://www.youtube.com/", route.response)
        self.assertIn("YouTube search fallback", route.response)
        self.assertIn("search_query=", route.response)

    def test_subject_aliases_and_unit_syllabus_are_detected(self) -> None:
        cases = {
            "Show DS Unit 2 syllabus": "BCS301",
            "Cyber Security unit 3 topics": "BCC301",
            "DSTL Unit 5 chapters": "BCS303",
            "Technical Communication unit 1 syllabus": "BAS301",
        }

        for message, subject_code in cases.items():
            with self.subTest(message=message):
                route = route_academic_message(message, self.subjects)
                self.assertEqual(route.kind, "direct")
                self.assertEqual(route.subject_code, subject_code)
                self.assertIn("Official syllabus topics", route.response)

    def test_credit_questions_use_numeric_catalog_values(self) -> None:
        filtered = route_academic_message(
            "Which subjects have 4 credits?",
            self.subjects,
        )
        one_subject = route_academic_message(
            "How many credits does Cyber Security have?",
            self.subjects,
        )

        self.assertIn("BCS301", filtered.response)
        self.assertIn("BCS302", filtered.response)
        self.assertNotIn("BCC301", filtered.response)
        self.assertIn("2 credit(s)", one_subject.response)

    def test_progress_updates_are_parsed_without_ollama(self) -> None:
        completed = route_academic_message(
            "I completed COA units 1 and 2",
            self.subjects,
        )
        removed = route_academic_message(
            "I haven't completed COA unit 2",
            self.subjects,
        )
        score = route_academic_message(
            "I scored 18/30 in COA",
            self.subjects,
        )

        self.assertEqual(completed.kind, "progress_update")
        self.assertEqual(completed.unit_numbers, (1, 2))
        self.assertEqual(completed.completed_action, "add")
        self.assertEqual(removed.completed_action, "remove")
        self.assertEqual(score.latest_score, 18)
        self.assertEqual(score.latest_score_max, 30)

    def test_relevant_unit_context_is_injected_for_explanations(self) -> None:
        route = route_academic_message(
            "Explain cache memory in COA",
            self.subjects,
        )
        context = build_academic_context(
            route,
            {
                "preparation_level": "basics_completed",
                "completed_units": [1, 2],
            },
        )

        self.assertEqual(route.kind, "context")
        self.assertEqual(route.unit_numbers, (4,))
        self.assertIn("Unit 4: Memory", context)
        self.assertIn("Credits: 4", context)
        self.assertIn("Completed units: 1, 2", context)
        self.assertIn("youtube.com", context)
        self.assertNotIn("Unit 3: Control Unit", context)

    def test_normal_conversation_is_not_hijacked(self) -> None:
        route = route_academic_message("Hello, how are you?", self.subjects)
        self.assertEqual(route.kind, "none")
        self.assertFalse(looks_like_academic_followup("Hello, how are you?"))

    def test_short_followup_can_reuse_a_previous_subject(self) -> None:
        self.assertTrue(looks_like_academic_followup("What about Unit 5 resources?"))
        route = route_academic_message(
            "What about Unit 5 resources? BCS302",
            self.subjects,
        )
        self.assertEqual(route.kind, "direct")
        self.assertEqual(route.subject_code, "BCS302")
        self.assertEqual(route.unit_numbers, (5,))

    def test_subject_only_correction_does_not_fall_through_to_ollama(self) -> None:
        route = route_academic_message("COA, I mean", self.subjects)
        self.assertEqual(route.kind, "direct")
        self.assertEqual(route.intent, "subject_reference")
        self.assertEqual(route.subject_code, "BCS302")

    def test_invalid_explanation_unit_is_rejected_before_ollama(self) -> None:
        route = route_academic_message("Explain COA Unit 9", self.subjects)
        self.assertEqual(route.kind, "direct")
        self.assertIn("has no Unit 9", route.response)

    def test_progress_summary_includes_credits_and_saved_state(self) -> None:
        text = format_progress_summary(
            self.subjects,
            {
                "BCS302": {
                    "preparation_level": "mostly_prepared",
                    "completed_units": [1, 2, 3],
                    "latest_score": 18,
                    "latest_score_max": 30,
                }
            },
            "BCS302",
        )

        self.assertIn("4 credit(s)", text)
        self.assertIn("Mostly prepared", text)
        self.assertIn("Completed units: 1, 2, 3", text)
        self.assertIn("18/30", text)


if __name__ == "__main__":
    unittest.main()
