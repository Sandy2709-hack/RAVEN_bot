import logging
import re
from datetime import date, datetime, time

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from attendance import (
    RAVEN_TIMEZONE,
    available_batch_groups,
    available_sections,
    find_schedule_entry,
    format_attendance_dashboard,
    india_today,
    list_attendance_subjects,
    load_matching_timetable,
    match_subject,
    parse_calendar_date,
    parse_cia_dates,
    schedule_for_date,
)
from keyboards import (
    attendance_batch_keyboard,
    attendance_menu_keyboard,
    attendance_section_keyboard,
    attendance_today_keyboard,
    bunk_class_picker_keyboard,
    bunk_outcome_keyboard,
)
from memory import (
    clear_attendance_events,
    deactivate_attendance_baselines,
    delete_attendance_event_for_entry,
    get_all_attendance_settings,
    get_attendance_event,
    get_attendance_event_for_entry,
    get_attendance_events_for_date,
    get_attendance_settings,
    get_attendance_totals,
    get_recent_attendance_events,
    get_student_profile,
    save_attendance_baseline,
    save_attendance_event,
    save_attendance_settings,
    undo_last_attendance_event,
    update_attendance_event_status,
)


logger = logging.getLogger("raven.attendance")


(
    ATTENDANCE_SECTION,
    ATTENDANCE_BATCH,
    ATTENDANCE_END_DATE,
    ATTENDANCE_CIA_DATES,
    ATTENDANCE_BASELINE,
) = range(5)


STATUS_LABELS = {
    "attended": "attended",
    "absent": "absent",
    "cancelled": "class/attendance cancelled",
    "planned_bunk": "mass-bunk outcome pending",
}


async def _reply_or_edit(update: Update, text: str, reply_markup=None) -> None:
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=reply_markup,
        )
    else:
        await update.effective_message.reply_text(text, reply_markup=reply_markup)


def _attendance_bundle(chat_id: int):
    settings = get_attendance_settings(chat_id)
    profile = get_student_profile(chat_id)
    timetable = load_matching_timetable(profile) if profile else None
    return settings, profile, timetable


def _dashboard_text(chat_id: int, settings: dict) -> str:
    return format_attendance_dashboard(
        get_attendance_totals(chat_id),
        section=settings["section"],
        batch_group=settings["batch_group"],
        target_percentage=settings["target_percentage"],
        cia_dates=settings["cia_dates"],
    )


async def start_attendance(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    if update.callback_query:
        await update.callback_query.answer()

    chat_id = update.effective_chat.id
    settings, profile, timetable = _attendance_bundle(chat_id)
    force_setup = bool(context.args and context.args[0].casefold() == "setup")
    if update.callback_query and update.callback_query.data == "attendance:setup":
        force_setup = True

    if not profile:
        await _reply_or_edit(update, "Create your student profile first with /setup.")
        return ConversationHandler.END
    if not timetable:
        await _reply_or_edit(
            update,
            "Raven does not have a verified timetable for your college, branch "
            "and semester yet.",
        )
        return ConversationHandler.END

    if settings and settings["setup_complete"] and not force_setup:
        await _reply_or_edit(
            update,
            _dashboard_text(chat_id, settings),
            reply_markup=attendance_menu_keyboard(),
        )
        return ConversationHandler.END

    context.user_data["attendance_setup"] = {
        "timetable": timetable,
        "semester_start": timetable["effective_from"],
        "target_percentage": 75.0,
        "reminder_time": "20:00",
        "reset_existing": settings is not None,
    }
    reset_notice = (
        "\n\n⚠️ Completing setup again will replace the current baseline and "
        "clear old daily attendance entries to prevent double-counting."
        if settings is not None
        else ""
    )
    await _reply_or_edit(
        update,
        "📊 ATTENDANCE SETUP\n\n"
        "I found the verified JSS CSE Semester 3 timetable effective from "
        f"{datetime.fromisoformat(timetable['effective_from']).strftime('%d %b %Y')}."
        f"{reset_notice}\n\nChoose your section:",
        reply_markup=attendance_section_keyboard(available_sections(timetable)),
    )
    return ATTENDANCE_SECTION


async def receive_attendance_section(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get("attendance_setup")
    if not draft:
        await query.edit_message_text("Attendance setup expired. Send /attendance.")
        return ConversationHandler.END

    section = query.data.rsplit(":", maxsplit=1)[1].upper()
    batch_groups = available_batch_groups(draft["timetable"], section)
    if not batch_groups:
        await query.edit_message_text("That section is not available in this timetable.")
        return ConversationHandler.END

    draft["section"] = section
    await query.edit_message_text(
        f"Section selected: {section}\n\nChoose your lab batch:",
        reply_markup=attendance_batch_keyboard(batch_groups),
    )
    return ATTENDANCE_BATCH


async def receive_attendance_batch(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get("attendance_setup")
    if not draft:
        await query.edit_message_text("Attendance setup expired. Send /attendance.")
        return ConversationHandler.END

    batch_group = query.data.rsplit(":", maxsplit=1)[1].upper()
    valid_batches = available_batch_groups(draft["timetable"], draft["section"])
    if batch_group not in valid_batches:
        await query.edit_message_text("That batch is not available for this section.")
        return ConversationHandler.END

    draft["batch_group"] = batch_group
    draft["subjects"] = list_attendance_subjects(
        draft["timetable"],
        draft["section"],
        batch_group,
    )
    await query.edit_message_text(
        f"✅ {draft['section']} • {batch_group}\n\n"
        "Send the semester end date as DD-MM-YYYY.\n"
        "If it has not been announced, send: skip"
    )
    return ATTENDANCE_END_DATE


async def receive_attendance_end_date(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    draft = context.user_data.get("attendance_setup")
    if not draft:
        await update.effective_message.reply_text(
            "Attendance setup expired. Send /attendance."
        )
        return ConversationHandler.END

    value = update.effective_message.text.strip()
    if value.casefold() == "skip":
        draft["semester_end"] = None
    else:
        try:
            semester_end = parse_calendar_date(value)
            if semester_end < date.fromisoformat(draft["semester_start"]):
                raise ValueError("Semester end cannot be before the timetable start")
        except ValueError as error:
            await update.effective_message.reply_text(f"⚠️ {error}")
            return ATTENDANCE_END_DATE
        draft["semester_end"] = semester_end.isoformat()

    await update.effective_message.reply_text(
        "Send the announced CIA/internal-exam dates separated by commas.\n"
        "Example: 15-09-2026, 20-11-2026\n\n"
        "If they are not announced, send: skip"
    )
    return ATTENDANCE_CIA_DATES


async def receive_attendance_cia_dates(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    draft = context.user_data.get("attendance_setup")
    if not draft:
        await update.effective_message.reply_text(
            "Attendance setup expired. Send /attendance."
        )
        return ConversationHandler.END

    value = update.effective_message.text.strip()
    try:
        cia_dates = [] if value.casefold() == "skip" else parse_cia_dates(value)
    except ValueError as error:
        await update.effective_message.reply_text(f"⚠️ {error}")
        return ATTENDANCE_CIA_DATES

    draft["cia_dates"] = [item.isoformat() for item in cia_dates]
    draft["subject_index"] = 0
    draft["baselines"] = []
    await _ask_for_next_baseline(update, draft)
    return ATTENDANCE_BASELINE


async def _ask_for_next_baseline(update: Update, draft: dict) -> None:
    subject = draft["subjects"][draft["subject_index"]]
    await update.effective_message.reply_text(
        f"📘 {subject['short_name']}\n"
        "Send: attended/conducted\n"
        "Example: 14/18\n\n"
        "Use ~14/18 if it is an estimate, or send skip if you do not take this subject."
    )


def _parse_baseline(value: str) -> tuple[int, int, bool] | None:
    text = value.strip().casefold()
    estimated = text.startswith("~") or "estimate" in text
    match = re.search(r"~?\s*(\d+)\s*/\s*(\d+)", text)
    if not match:
        return None
    attended, conducted = int(match.group(1)), int(match.group(2))
    if attended > conducted:
        return None
    return attended, conducted, estimated


async def receive_attendance_baseline(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    draft = context.user_data.get("attendance_setup")
    if not draft:
        await update.effective_message.reply_text(
            "Attendance setup expired. Send /attendance."
        )
        return ConversationHandler.END

    subject = draft["subjects"][draft["subject_index"]]
    value = update.effective_message.text.strip()
    if value.casefold() == "skip":
        attended, conducted, estimated, active = 0, 0, False, False
    else:
        parsed = _parse_baseline(value)
        if parsed is None:
            await update.effective_message.reply_text(
                "Send values like 14/18, ~14/18 for an estimate, or skip."
            )
            return ATTENDANCE_BASELINE
        attended, conducted, estimated = parsed
        active = True

    draft["baselines"].append(
        {
            "subject": subject,
            "attended": attended,
            "conducted": conducted,
            "estimated": estimated,
            "active": active,
            "display_order": draft["subject_index"],
        }
    )
    draft["subject_index"] += 1

    if draft["subject_index"] < len(draft["subjects"]):
        await _ask_for_next_baseline(update, draft)
        return ATTENDANCE_BASELINE

    chat_id = update.effective_chat.id
    save_attendance_settings(
        chat_id=chat_id,
        section=draft["section"],
        batch_group=draft["batch_group"],
        semester_start=draft["semester_start"],
        semester_end=draft.get("semester_end"),
        cia_dates=draft["cia_dates"],
        target_percentage=draft["target_percentage"],
        reminder_time=draft["reminder_time"],
        setup_complete=False,
    )
    if draft["reset_existing"]:
        clear_attendance_events(chat_id)
    deactivate_attendance_baselines(chat_id)
    for baseline in draft["baselines"]:
        item = baseline["subject"]
        save_attendance_baseline(
            chat_id=chat_id,
            subject_code=item["subject_code"],
            subject_name=item["name"],
            short_name=item["short_name"],
            attended=baseline["attended"],
            conducted=baseline["conducted"],
            estimated=baseline["estimated"],
            active=baseline["active"],
            display_order=baseline["display_order"],
        )
    settings = save_attendance_settings(
        chat_id=chat_id,
        section=draft["section"],
        batch_group=draft["batch_group"],
        semester_start=draft["semester_start"],
        semester_end=draft.get("semester_end"),
        cia_dates=draft["cia_dates"],
        target_percentage=draft["target_percentage"],
        reminder_time=draft["reminder_time"],
        setup_complete=True,
    )
    context.user_data.pop("attendance_setup", None)
    schedule_attendance_reminder(context.application, settings)
    await update.effective_message.reply_text(
        "✅ Attendance setup complete.\n\n" + _dashboard_text(
            update.effective_chat.id,
            settings,
        ),
        reply_markup=attendance_menu_keyboard(),
    )
    return ConversationHandler.END


async def cancel_attendance_setup(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    context.user_data.pop("attendance_setup", None)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Attendance setup cancelled.")
    else:
        await update.effective_message.reply_text("Attendance setup cancelled.")
    return ConversationHandler.END


def attendance_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("attendance", start_attendance),
            CallbackQueryHandler(start_attendance, pattern=r"^menu:attendance$"),
            CallbackQueryHandler(start_attendance, pattern=r"^attendance:setup$"),
        ],
        states={
            ATTENDANCE_SECTION: [
                CallbackQueryHandler(
                    receive_attendance_section,
                    pattern=r"^attsetup:section:[A-Z0-9]+$",
                )
            ],
            ATTENDANCE_BATCH: [
                CallbackQueryHandler(
                    receive_attendance_batch,
                    pattern=r"^attsetup:batch:[A-Z0-9]+$",
                )
            ],
            ATTENDANCE_END_DATE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_attendance_end_date,
                )
            ],
            ATTENDANCE_CIA_DATES: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_attendance_cia_dates,
                )
            ],
            ATTENDANCE_BASELINE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_attendance_baseline,
                )
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_attendance_setup),
            CallbackQueryHandler(
                cancel_attendance_setup,
                pattern=r"^attsetup:cancel$",
            ),
        ],
        allow_reentry=True,
    )


def _today_payload(chat_id: int, class_date: date):
    settings, profile, timetable = _attendance_bundle(chat_id)
    if not settings or not settings["setup_complete"] or not timetable:
        return None
    entries = schedule_for_date(
        timetable,
        settings["section"],
        settings["batch_group"],
        class_date,
    )
    active_codes = {
        item["subject_code"]
        for item in get_attendance_totals(chat_id)
    }
    entries = [
        entry for entry in entries if entry["subject_code"] in active_codes
    ]
    events = get_attendance_events_for_date(chat_id, class_date.isoformat())
    successful_mass_bunks = {
        event["timetable_entry_id"]
        for event in events
        if event["status"] == "cancelled" and event["source"] == "bunk_command"
    }
    entries = [
        entry
        for entry in entries
        if entry["id"] not in successful_mass_bunks
    ]
    status_by_entry = {
        event["timetable_entry_id"]: event["status"]
        for event in events
    }
    return settings, timetable, entries, status_by_entry


def _today_text(class_date: date, entries: list[dict], status_by_entry: dict) -> str:
    if not entries:
        return (
            f"📋 {class_date.strftime('%A, %d %b')}\n\n"
            "No attendance-tracked classes are scheduled."
        )
    unresolved = sum(
        1
        for entry in entries
        if status_by_entry.get(entry["id"]) in {None, "planned_bunk"}
    )
    return (
        f"📋 ATTENDANCE CHECK - {class_date.strftime('%A, %d %b')}\n\n"
        "Tap a class repeatedly to cycle:\n"
        "⬜ Not entered → ✅ Attended → ❌ Absent → 🚫 Cancelled\n\n"
        f"Unresolved classes: {unresolved}"
    )


async def attendance_action_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", maxsplit=1)[1]
    chat_id = update.effective_chat.id
    settings = get_attendance_settings(chat_id)
    if not settings or not settings["setup_complete"]:
        await query.edit_message_text("Send /attendance to complete setup first.")
        return

    if action == "dashboard":
        await query.edit_message_text(
            _dashboard_text(chat_id, settings),
            reply_markup=attendance_menu_keyboard(),
        )
        return

    if action == "today":
        class_date = india_today()
        payload = _today_payload(chat_id, class_date)
        if not payload:
            await query.edit_message_text("Attendance setup could not be loaded.")
            return
        _, _, entries, status_by_entry = payload
        await query.edit_message_text(
            _today_text(class_date, entries, status_by_entry),
            reply_markup=(
                attendance_today_keyboard(
                    entries,
                    status_by_entry,
                    class_date.isoformat(),
                )
                if entries
                else attendance_menu_keyboard()
            ),
        )
        return

    if action == "history":
        events = get_recent_attendance_events(chat_id, limit=12)
        if not events:
            text = "📜 ATTENDANCE HISTORY\n\nNo daily entries yet."
        else:
            lines = ["📜 ATTENDANCE HISTORY", ""]
            for event in events:
                lines.append(
                    f"#{event['id']} • {event['class_date']} • "
                    f"{event['subject_code']} • "
                    f"{STATUS_LABELS[event['status']]} ×{event['class_count']}"
                )
            text = "\n".join(lines)
        await query.edit_message_text(text, reply_markup=attendance_menu_keyboard())
        return

    if action == "undo":
        event = undo_last_attendance_event(chat_id)
        text = (
            f"↩️ Removed {event['subject_code']} - "
            f"{STATUS_LABELS[event['status']]} on {event['class_date']}."
            if event
            else "There is no attendance entry to undo."
        )
        await query.edit_message_text(text, reply_markup=attendance_menu_keyboard())


async def attendance_event_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    chat_id = update.effective_chat.id

    if parts[1] in {"cycle", "done", "bunkpick"}:
        class_date = datetime.strptime(parts[2], "%Y%m%d").date()
        payload = _today_payload(chat_id, class_date)
        if not payload:
            await query.edit_message_text("Attendance setup could not be loaded.")
            return
        settings, timetable, entries, status_by_entry = payload

    if parts[1] == "cycle":
        entry_id = parts[3]
        entry = find_schedule_entry(
            timetable,
            settings["section"],
            settings["batch_group"],
            class_date,
            entry_id,
        )
        if not entry:
            await query.edit_message_text("That timetable class could not be found.")
            return

        existing = get_attendance_event_for_entry(
            chat_id,
            class_date.isoformat(),
            entry_id,
        )
        current_status = existing["status"] if existing else None
        next_status = {
            None: "attended",
            "attended": "absent",
            "absent": "cancelled",
            "cancelled": None,
            "planned_bunk": "cancelled",
        }[current_status]
        if next_status is None:
            delete_attendance_event_for_entry(
                chat_id,
                class_date.isoformat(),
                entry_id,
            )
        elif existing:
            update_attendance_event_status(
                chat_id=chat_id,
                event_id=existing["id"],
                status=next_status,
            )
        else:
            save_attendance_event(
                chat_id=chat_id,
                subject_code=entry["subject_code"],
                class_date=class_date.isoformat(),
                timetable_entry_id=entry_id,
                period_label=entry["period_label"],
                class_count=entry["class_count"],
                status=next_status,
            )

        refreshed = _today_payload(chat_id, class_date)
        _, _, entries, status_by_entry = refreshed
        await query.edit_message_text(
            _today_text(class_date, entries, status_by_entry),
            reply_markup=attendance_today_keyboard(
                entries,
                status_by_entry,
                class_date.isoformat(),
            ),
        )
        return

    if parts[1] == "done":
        unresolved = [
            entry
            for entry in entries
            if status_by_entry.get(entry["id"]) in {None, "planned_bunk"}
        ]
        if unresolved:
            await query.edit_message_text(
                _today_text(class_date, entries, status_by_entry)
                + f"\n\n⚠️ Resolve all {len(unresolved)} remaining classes first.",
                reply_markup=attendance_today_keyboard(
                    entries,
                    status_by_entry,
                    class_date.isoformat(),
                ),
            )
            return
        await query.edit_message_text(
            "✅ Today's attendance is complete.\n\n"
            + _dashboard_text(chat_id, settings),
            reply_markup=attendance_menu_keyboard(),
        )
        return

    if parts[1] == "bunkpick":
        entry_id = parts[3]
        entry = find_schedule_entry(
            timetable,
            settings["section"],
            settings["batch_group"],
            class_date,
            entry_id,
        )
        if not entry:
            await query.edit_message_text("That timetable class could not be found.")
            return
        event = _save_planned_bunk(chat_id, class_date, entry)
        await query.edit_message_text(
            f"🐦‍⬛ {entry['subject']['short_name']} {entry['period_label']} "
            "is marked as a planned bunk.\n\nWhat actually happened?",
            reply_markup=bunk_outcome_keyboard(event["id"]),
        )
        return

    if parts[1] == "bunkout":
        event_id = int(parts[2])
        outcome = parts[3]
        event = get_attendance_event(event_id, chat_id)
        if not event or event["source"] != "bunk_command":
            await query.edit_message_text("That bunk record could not be found.")
            return
        saved = update_attendance_event_status(
            chat_id=chat_id,
            event_id=event_id,
            status=outcome,
        )
        await query.edit_message_text(
            f"✅ {saved['subject_code']} recorded as "
            f"{STATUS_LABELS[saved['status']]}.\n\n"
            + _dashboard_text(chat_id, get_attendance_settings(chat_id)),
            reply_markup=attendance_menu_keyboard(),
        )


def _save_planned_bunk(chat_id: int, class_date: date, entry: dict) -> dict:
    return save_attendance_event(
        chat_id=chat_id,
        subject_code=entry["subject_code"],
        class_date=class_date.isoformat(),
        timetable_entry_id=entry["id"],
        period_label=entry["period_label"],
        class_count=entry["class_count"],
        status="planned_bunk",
        source="bunk_command",
    )


async def bunk_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    chat_id = update.effective_chat.id
    settings, profile, timetable = _attendance_bundle(chat_id)
    if not settings or not settings["setup_complete"] or not timetable:
        await update.effective_message.reply_text(
            "Complete attendance setup first with /attendance."
        )
        return

    query_text = " ".join(context.args).strip()
    subjects = list_attendance_subjects(
        timetable,
        settings["section"],
        settings["batch_group"],
    )
    active_codes = {
        item["subject_code"]
        for item in get_attendance_totals(chat_id)
    }
    subjects = [
        subject
        for subject in subjects
        if subject["subject_code"] in active_codes
    ]
    subject = match_subject(query_text, subjects)
    if not subject:
        choices = ", ".join(item["short_name"] for item in subjects)
        await update.effective_message.reply_text(
            "Usage: /bunk <subject>\n"
            "Example: /bunk COA\n\n"
            f"Available subjects: {choices}"
        )
        return

    class_date = india_today()
    matches = [
        entry
        for entry in schedule_for_date(
            timetable,
            settings["section"],
            settings["batch_group"],
            class_date,
        )
        if entry["subject_code"] == subject["subject_code"]
    ]
    if not matches:
        await update.effective_message.reply_text(
            f"{subject['short_name']} is not scheduled today "
            f"({class_date.strftime('%A')})."
        )
        return

    unresolved = [
        entry
        for entry in matches
        if get_attendance_event_for_entry(
            chat_id,
            class_date.isoformat(),
            entry["id"],
        ) is None
    ]
    if not unresolved:
        await update.effective_message.reply_text(
            f"Today's {subject['short_name']} attendance is already recorded. "
            "Use Attendance → Today's Classes to change it."
        )
        return

    if len(unresolved) > 1:
        await update.effective_message.reply_text(
            "Which scheduled class are you planning to bunk?",
            reply_markup=bunk_class_picker_keyboard(
                unresolved,
                class_date.isoformat(),
            ),
        )
        return

    entry = unresolved[0]
    event = _save_planned_bunk(chat_id, class_date, entry)
    await update.effective_message.reply_text(
        f"🐦‍⬛ Planned bunk: {subject['short_name']} • "
        f"{entry['period_label']} • {entry['time_label']}\n\n"
        "What actually happened? You can also choose Decide later.",
        reply_markup=bunk_outcome_keyboard(event["id"]),
    )


async def send_daily_attendance_check(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    chat_id = context.job.chat_id
    class_date = india_today()
    payload = _today_payload(chat_id, class_date)
    if not payload:
        return
    _, _, entries, status_by_entry = payload
    unresolved = [
        entry
        for entry in entries
        if status_by_entry.get(entry["id"]) in {None, "planned_bunk"}
    ]
    if not unresolved:
        return
    await context.bot.send_message(
        chat_id=chat_id,
        text=_today_text(class_date, entries, status_by_entry),
        reply_markup=attendance_today_keyboard(
            entries,
            status_by_entry,
            class_date.isoformat(),
        ),
    )


def schedule_attendance_reminder(application, settings: dict) -> None:
    job_queue = application.job_queue
    if job_queue is None:
        logger.warning(
            "Attendance reminders require python-telegram-bot[job-queue]"
        )
        return

    job_name = f"attendance-daily-{settings['chat_id']}"
    for existing in job_queue.get_jobs_by_name(job_name):
        existing.schedule_removal()

    hour_text, minute_text = settings["reminder_time"].split(":", maxsplit=1)
    job_queue.run_daily(
        send_daily_attendance_check,
        time=time(
            hour=int(hour_text),
            minute=int(minute_text),
            tzinfo=RAVEN_TIMEZONE,
        ),
        name=job_name,
        chat_id=settings["chat_id"],
    )


async def register_attendance_jobs(application) -> None:
    for settings in get_all_attendance_settings(complete_only=True):
        schedule_attendance_reminder(application, settings)
