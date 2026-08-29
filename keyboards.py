from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💬 Chat", callback_data="menu:chat"),
                InlineKeyboardButton("📚 Academics", callback_data="menu:academics"),
            ],
            [
                InlineKeyboardButton("🛠 Projects", callback_data="menu:projects"),
                InlineKeyboardButton("🌱 Personal Growth", callback_data="menu:growth"),
            ],
            [
                InlineKeyboardButton("🤝 Community", callback_data="menu:community"),
                InlineKeyboardButton("👤 My Profile", callback_data="menu:profile"),
            ],
        ]
    )


def academics_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🚨 COA Exam Rescue",
                    callback_data="menu:exam_rescue",
                )
            ],
            [
                InlineKeyboardButton(
                    "📘 COA Syllabus",
                    callback_data="menu:syllabus",
                ),
                InlineKeyboardButton(
                    "📖 Resources",
                    callback_data="menu:resources",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📊 Attendance",
                    callback_data="menu:attendance",
                ),
                InlineKeyboardButton(
                    "📢 JSS/AKTU Updates",
                    callback_data="menu:updates",
                ),
            ],
            [InlineKeyboardButton("⬅️ Main Menu", callback_data="menu:main")],
        ]
    )


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Main Menu", callback_data="menu:main")]]
    )


def back_to_academics_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Academics", callback_data="menu:academics")]]
    )


def completed_units_keyboard(selected_units: set[int]) -> InlineKeyboardMarkup:
    rows = []

    for start in (1, 3, 5):
        row = []
        for unit in range(start, min(start + 2, 6)):
            marker = "✅" if unit in selected_units else "⬜"
            row.append(
                InlineKeyboardButton(
                    f"{marker} Unit {unit}",
                    callback_data=f"rescue:unit:{unit}",
                )
            )
        rows.append(row)

    rows.append(
        [InlineKeyboardButton("Continue ➡️", callback_data="rescue:units_done")]
    )
    rows.append(
        [InlineKeyboardButton("Cancel", callback_data="rescue:cancel")]
    )
    return InlineKeyboardMarkup(rows)


def target_score_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("40+", callback_data="rescue:target:40"),
                InlineKeyboardButton("50+", callback_data="rescue:target:50"),
            ],
            [
                InlineKeyboardButton("60+", callback_data="rescue:target:60"),
                InlineKeyboardButton("70+", callback_data="rescue:target:70"),
            ],
            [InlineKeyboardButton("Cancel", callback_data="rescue:cancel")],
        ]
    )
