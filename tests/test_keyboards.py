import sys
import types
import unittest


class FakeInlineKeyboardButton:
    def __init__(self, text: str, callback_data: str) -> None:
        self.text = text
        self.callback_data = callback_data


class FakeInlineKeyboardMarkup:
    def __init__(self, inline_keyboard: list[list[FakeInlineKeyboardButton]]) -> None:
        self.inline_keyboard = inline_keyboard


fake_telegram = types.ModuleType("telegram")
fake_telegram.InlineKeyboardButton = FakeInlineKeyboardButton
fake_telegram.InlineKeyboardMarkup = FakeInlineKeyboardMarkup
sys.modules.setdefault("telegram", fake_telegram)

from keyboards import academics_menu_keyboard, subject_picker_keyboard


class KeyboardTests(unittest.TestCase):
    def test_academics_menu_uses_feature_first_hierarchy(self) -> None:
        keyboard = academics_menu_keyboard().inline_keyboard
        labels = [button.text for row in keyboard for button in row]

        self.assertIn("🚨 Exam Rescue", labels)
        self.assertIn("📘 Syllabus", labels)
        self.assertNotIn("🚨 COA Exam Rescue", labels)

    def test_subject_picker_marks_available_and_planned_subjects(self) -> None:
        subjects = [
            {
                "subject_code": "BCS302",
                "short_name": "COA",
                "status": "available",
            },
            {
                "subject_code": "BCS301",
                "short_name": "Data Structures",
                "status": "planned",
            },
        ]
        keyboard = subject_picker_keyboard("syllabus", subjects).inline_keyboard

        self.assertEqual(keyboard[0][0].callback_data, "academic:syllabus:BCS302")
        self.assertIn("✅", keyboard[0][0].text)
        self.assertIn("🔒", keyboard[1][0].text)


if __name__ == "__main__":
    unittest.main()
