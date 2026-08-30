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
                )
            ],
            [
                InlineKeyboardButton(
                    "📘 Syllabus",
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


def subject_picker_keyboard(
    feature: str,
    subjects: list[dict],
) -> InlineKeyboardMarkup:
    rows = []

    for subject in subjects:
        if subject["status"] == "available":
            marker = "✅"
            credits = subject.get("credits")
            credit_text = f" • {credits} cr" if credits is not None else ""
            suffix = f"({subject['subject_code']}){credit_text}"
        else:
            marker = "🔒"
            suffix = "— soon"

        rows.append(
            [
                InlineKeyboardButton(
                    f"{marker} {subject['short_name']} {suffix}",
                    callback_data=(
                        f"academic:{feature}:{subject['subject_code']}"
                    ),
                )
            ]
        )

    rows.append([InlineKeyboardButton("⬅️ Academics", callback_data="menu:academics")])
    return InlineKeyboardMarkup(rows)


def back_to_subjects_keyboard(feature: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Subjects", callback_data=f"menu:{feature}")]]
    )


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Main Menu", callback_data="menu:main")]]
    )


def back_to_academics_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Academics", callback_data="menu:academics")]]
    )


def attendance_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📊 Dashboard",
                    callback_data="attendance:dashboard",
                ),
                InlineKeyboardButton(
                    "📋 Today's Classes",
                    callback_data="attendance:today",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📜 History",
                    callback_data="attendance:history",
                ),
                InlineKeyboardButton(
                    "↩️ Undo Last",
                    callback_data="attendance:undo",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⚙️ Set Up Again",
                    callback_data="attendance:setup",
                )
            ],
            [InlineKeyboardButton("⬅️ Academics", callback_data="menu:academics")],
        ]
    )


def attendance_section_keyboard(sections: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                section,
                callback_data=f"attsetup:section:{section}",
            )
        ]
        for section in sections
    ]
    rows.append(
        [InlineKeyboardButton("Cancel", callback_data="attsetup:cancel")]
    )
    return InlineKeyboardMarkup(rows)


def attendance_batch_keyboard(batch_groups: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                batch,
                callback_data=f"attsetup:batch:{batch}",
            )
        ]
        for batch in batch_groups
    ]
    rows.append(
        [InlineKeyboardButton("Cancel", callback_data="attsetup:cancel")]
    )
    return InlineKeyboardMarkup(rows)


def attendance_today_keyboard(
    entries: list[dict],
    status_by_entry: dict[str, str],
    class_date: str,
) -> InlineKeyboardMarkup:
    markers = {
        "attended": "✅",
        "absent": "❌",
        "cancelled": "🚫",
        "planned_bunk": "🐦‍⬛",
    }
    compact_date = class_date.replace("-", "")
    rows = []
    for entry in entries:
        status = status_by_entry.get(entry["id"])
        marker = markers.get(status, "⬜")
        label = (
            f"{marker} {entry['subject']['short_name']} • "
            f"{entry['period_label']} • {entry['time_label']}"
        )
        rows.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=f"att:cycle:{compact_date}:{entry['id']}",
                )
            ]
        )
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    "Done ✅",
                    callback_data=f"att:done:{compact_date}",
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Attendance",
                    callback_data="attendance:dashboard",
                )
            ],
        ]
    )
    return InlineKeyboardMarkup(rows)


def bunk_class_picker_keyboard(
    entries: list[dict],
    class_date: str,
) -> InlineKeyboardMarkup:
    compact_date = class_date.replace("-", "")
    rows = [
        [
            InlineKeyboardButton(
                f"{entry['subject']['short_name']} • {entry['period_label']} • "
                f"{entry['time_label']}",
                callback_data=f"att:bunkpick:{compact_date}:{entry['id']}",
            )
        ]
        for entry in entries
    ]
    rows.append(
        [InlineKeyboardButton("Cancel", callback_data="attendance:dashboard")]
    )
    return InlineKeyboardMarkup(rows)


def bunk_outcome_keyboard(event_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🐦‍⬛ Class/attendance cancelled",
                    callback_data=f"att:bunkout:{event_id}:cancelled",
                )
            ],
            [
                InlineKeyboardButton(
                    "🙋 I attended",
                    callback_data=f"att:bunkout:{event_id}:attended",
                ),
                InlineKeyboardButton(
                    "❌ Marked absent",
                    callback_data=f"att:bunkout:{event_id}:absent",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⏰ Decide later",
                    callback_data="attendance:dashboard",
                )
            ],
        ]
    )


def completed_units_keyboard(
    selected_units: set[int],
    unit_numbers: list[int] | None = None,
) -> InlineKeyboardMarkup:
    rows = []
    unit_numbers = unit_numbers or list(range(1, 6))

    for index in range(0, len(unit_numbers), 2):
        row = []
        for unit in unit_numbers[index:index + 2]:
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
