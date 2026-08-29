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
                    "🚨 Exam Rescue",
                    callback_data="menu:exam_rescue",
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
