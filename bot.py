import asyncio
import logging
from contextlib import closing

import requests
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import (
    LONG_TERM_MEMORY_LIMIT,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
    OLLAMA_URL,
    RECENT_MESSAGE_LIMIT,
    TELEGRAM_BOT_TOKEN,
    validate_settings,
)
from academics import (
    build_exam_rescue_plan,
    format_exam_rescue_plan,
    format_subject_resources,
    format_subject_syllabus,
    list_all_subjects,
    list_subjects,
    load_subject,
)

from academic_router import (
    AcademicRoute,
    PREPARATION_LEVEL_LABELS,
    build_academic_context,
    detect_subject_code,
    format_progress_summary,
    infer_preparation_level,
    looks_like_academic_followup,
    route_academic_message,
)
from keyboards import (
    academics_menu_keyboard,
    back_to_academics_keyboard,
    back_to_menu_keyboard,
    back_to_subjects_keyboard,
    completed_units_keyboard,
    main_menu_keyboard,
    subject_picker_keyboard,
    target_score_keyboard,
)
from memory import (
    clear_chat_history,
    clear_memories,
    delete_memory,
    get_memories,
    get_recent_messages,
    get_all_subject_progress,
    get_latest_exam_rescue_plan,
    get_subject_progress,
    get_student_profile,
    init_db,
    save_memory,
    save_message,
    save_exam_rescue_plan,
    save_subject_progress,
    save_student_profile,
)


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("raven")


(
    PROFILE_COLLEGE,
    PROFILE_BRANCH,
    PROFILE_YEAR,
    PROFILE_SEMESTER,
    RESCUE_DAYS,
    RESCUE_COMPLETED,
    RESCUE_TARGET,
) = range(7)


SYSTEM_PROMPT = """
You are Raven, a practical AI college companion.

Your personality:
- Friendly, casual and straightforward.
- Keep answers concise unless the user asks for detail.
- Use Hinglish naturally when the user uses Hinglish.
- Never pretend to be human.
- Do not claim that an unfinished Raven feature already works.

You may receive recent conversation history and long-term user memories.
Use those memories only when they are relevant. Do not mention the memory
system unless the user asks about it.

You may also receive a trusted RAVEN ACADEMIC CONTEXT block retrieved from
Raven's local catalog. Use its exact syllabus, credits, progress and resource
links. Never claim you cannot access information explicitly present there.
Never invent missing academic data or PYQ importance.
""".strip()


def ask_ollama(messages: list[dict[str, str]]) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "think": False,
        "keep_alive": "30m",
        "options": {
            "num_ctx": 4096,
            "num_predict": 200,
        },
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=OLLAMA_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()

    total_seconds = data.get("total_duration", 0) / 1_000_000_000
    load_seconds = data.get("load_duration", 0) / 1_000_000_000
    prompt_seconds = data.get("prompt_eval_duration", 0) / 1_000_000_000
    generation_seconds = data.get("eval_duration", 0) / 1_000_000_000
    eval_count = data.get("eval_count", 0)
    tokens_per_second = (
        eval_count / generation_seconds if generation_seconds > 0 else 0
    )

    logger.info(
        "Ollama total=%.2fs load=%.2fs prompt=%.2fs generation=%.2fs speed=%.2f tok/s",
        total_seconds,
        load_seconds,
        prompt_seconds,
        generation_seconds,
        tokens_per_second,
    )

    return data["message"]["content"].strip()


def build_memory_context(memories: list[dict]) -> str:
    if not memories:
        return ""

    lines = [
        f"- [{memory['category']}] {memory['content']}"
        for memory in memories
    ]
    return "\n\nLONG-TERM MEMORY ABOUT THE USER:\n" + "\n".join(lines)


def format_profile(profile: dict) -> str:
    username = profile.get("telegram_username")
    username_line = f"@{username}" if username else "Not set"

    return (
        "👤 YOUR RAVEN PROFILE\n\n"
        f"Name: {profile['full_name']}\n"
        f"Telegram: {username_line}\n"
        f"College: {profile['college']}\n"
        f"Branch: {profile['branch']}\n"
        f"Year: {profile['academic_year']}\n"
        f"Semester: {profile['semester']}"
    )


async def send_in_chunks(message, text: str, chunk_size: int = 3800) -> None:
    remaining = text

    while remaining:
        if len(remaining) <= chunk_size:
            chunk = remaining
            remaining = ""
        else:
            split_at = remaining.rfind("\n", 0, chunk_size)
            if split_at < chunk_size // 2:
                split_at = chunk_size
            chunk = remaining[:split_at]
            remaining = remaining[split_at:].lstrip("\n")

        await message.reply_text(chunk)


async def begin_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    user = update.effective_user

    context.user_data["profile_draft"] = {
        "telegram_user_id": user.id,
        "telegram_username": user.username,
        "full_name": user.full_name,
    }

    await message.reply_text(
        "🐦‍⬛ Welcome to Raven.\n\n"
        "Before we begin, I need a short academic profile so future resources, "
        "deadlines and exam plans can be relevant to you.\n\n"
        "Which college are you studying in?\n"
        "Example: JSS Academy of Technical Education, Noida\n\n"
        "Send /cancel to stop setup."
    )
    return PROFILE_COLLEGE


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    profile = get_student_profile(chat_id)

    if not profile:
        return await begin_onboarding(update, context)

    first_name = update.effective_user.first_name
    await update.effective_message.reply_text(
        f"🐦‍⬛ Welcome back, {first_name}. What do you need?",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END


async def setup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await begin_onboarding(update, context)


async def receive_college(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    college = update.effective_message.text.strip()

    if len(college) < 2 or len(college) > 120:
        await update.effective_message.reply_text(
            "Please enter a valid college name (2–120 characters)."
        )
        return PROFILE_COLLEGE

    context.user_data["profile_draft"]["college"] = college
    await update.effective_message.reply_text(
        "What is your branch?\nExample: CSE, IT, ECE or ME"
    )
    return PROFILE_BRANCH


async def receive_branch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    branch = update.effective_message.text.strip().upper()

    if len(branch) < 2 or len(branch) > 40:
        await update.effective_message.reply_text(
            "Please enter a valid branch name or abbreviation."
        )
        return PROFILE_BRANCH

    context.user_data["profile_draft"]["branch"] = branch
    await update.effective_message.reply_text(
        "Which year are you currently in? Send a number from 1 to 4."
    )
    return PROFILE_YEAR


async def receive_year(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        academic_year = int(update.effective_message.text.strip())
    except ValueError:
        academic_year = 0

    if academic_year not in range(1, 5):
        await update.effective_message.reply_text(
            "Please send only 1, 2, 3 or 4 for your current year."
        )
        return PROFILE_YEAR

    context.user_data["profile_draft"]["academic_year"] = academic_year
    await update.effective_message.reply_text(
        "Which semester are you currently in? Send a number from 1 to 8."
    )
    return PROFILE_SEMESTER


async def receive_semester(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        semester = int(update.effective_message.text.strip())
    except ValueError:
        semester = 0

    if semester not in range(1, 9):
        await update.effective_message.reply_text(
            "Please send a semester number from 1 to 8."
        )
        return PROFILE_SEMESTER

    draft = context.user_data.get("profile_draft", {})
    required = {
        "telegram_user_id",
        "full_name",
        "college",
        "branch",
        "academic_year",
    }

    if not required.issubset(draft):
        context.user_data.pop("profile_draft", None)
        await update.effective_message.reply_text(
            "Your setup session expired. Send /setup to begin again."
        )
        return ConversationHandler.END

    save_student_profile(
        chat_id=update.effective_chat.id,
        telegram_user_id=draft["telegram_user_id"],
        telegram_username=draft.get("telegram_username"),
        full_name=draft["full_name"],
        college=draft["college"],
        branch=draft["branch"],
        academic_year=draft["academic_year"],
        semester=semester,
    )
    context.user_data.pop("profile_draft", None)

    await update.effective_message.reply_text(
        "✅ Your Raven profile is ready.\n\n"
        "Your profile will be used to personalize Academic features and future updates.",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END


async def cancel_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("profile_draft", None)
    await update.effective_message.reply_text(
        "Setup cancelled. Send /setup whenever you want to continue."
    )
    return ConversationHandler.END


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = get_student_profile(update.effective_chat.id)

    if not profile:
        await update.effective_message.reply_text(
            "You need a student profile first. Send /setup."
        )
        return

    await update.effective_message.reply_text(
        "🐦‍⬛ RAVEN — MAIN MENU",
        reply_markup=main_menu_keyboard(),
    )


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = get_student_profile(update.effective_chat.id)

    if not profile:
        await update.effective_message.reply_text(
            "No student profile found. Send /setup to create one."
        )
        return

    await update.effective_message.reply_text(
        format_profile(profile) + "\n\nUse /setup to update it.",
        reply_markup=back_to_menu_keyboard(),
    )


async def start_exam_rescue(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query
    await query.answer()

    profile = get_student_profile(update.effective_chat.id)
    if not profile:
        await query.edit_message_text(
            "You need a student profile before creating a plan. Send /setup."
        )
        return ConversationHandler.END

    subject_code = query.data.rsplit(":", maxsplit=1)[1].upper()
    profile_subjects = {
        subject["subject_code"]: subject
        for subject in list_subjects(
            profile["branch"],
            profile["semester"],
            feature="exam_rescue",
        )
    }
    metadata = profile_subjects.get(subject_code)

    if not metadata:
        await query.edit_message_text(
            "That subject is not available for your current branch and semester.",
            reply_markup=back_to_subjects_keyboard("exam_rescue"),
        )
        return ConversationHandler.END

    if metadata["status"] != "available":
        await query.edit_message_text(
            f"🔒 {metadata['short_name']} Exam Rescue is coming soon.\n\n"
            "Choose one of the currently available subjects.",
            reply_markup=back_to_subjects_keyboard("exam_rescue"),
        )
        return ConversationHandler.END

    subject = load_subject(subject_code)
    unit_numbers = [unit["number"] for unit in subject["units"]]
    progress = get_subject_progress(update.effective_chat.id, subject_code)
    completed_units = set((progress or {}).get("completed_units", []))
    context.user_data["rescue_draft"] = {
        "subject_code": subject_code,
        "subject_short_name": subject["short_name"],
        "unit_numbers": unit_numbers,
        "completed_units": completed_units,
    }
    await query.edit_message_text(
        f"🚨 {subject['short_name']} EXAM RESCUE\n\n"
        f"Raven will create a syllabus-based plan for {subject['subject_code']} "
        "using the official AKTU curriculum and verified free resources.\n\n"
        "How many days remain before the exam?\n"
        "Send a number from 1 to 30.\n\n"
        "Send /cancel to stop."
    )
    return RESCUE_DAYS


async def receive_rescue_days(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    try:
        days = int(update.effective_message.text.strip())
    except ValueError:
        days = 0

    if days not in range(1, 31):
        await update.effective_message.reply_text(
            "Please send the number of remaining days from 1 to 30."
        )
        return RESCUE_DAYS

    draft = context.user_data.get("rescue_draft")
    if not draft:
        await update.effective_message.reply_text(
            "Your Exam Rescue session expired. Open /menu and start it again."
        )
        return ConversationHandler.END

    draft["days"] = days
    short_name = draft["subject_short_name"]
    selected = draft["completed_units"]
    selected_text = ", ".join(map(str, sorted(selected))) if selected else "None"
    await update.effective_message.reply_text(
        f"Which {short_name} units have you already completed?\n\n"
        f"Saved selection: {selected_text}\n\n"
        "Tap units to select or unselect them, then press Continue. "
        "Leave every unit unchecked if you are starting from zero.",
        reply_markup=completed_units_keyboard(selected, draft["unit_numbers"]),
    )
    return RESCUE_COMPLETED


async def toggle_completed_unit(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get("rescue_draft")

    if not draft:
        await query.edit_message_text(
            "Your Exam Rescue session expired. Open /menu and start it again."
        )
        return ConversationHandler.END

    unit_number = int(query.data.rsplit(":", maxsplit=1)[1])
    if unit_number not in draft["unit_numbers"]:
        await query.edit_message_text(
            "That unit is not part of this subject. Start Exam Rescue again."
        )
        return RESCUE_COMPLETED

    selected = draft.setdefault("completed_units", set())

    if unit_number in selected:
        selected.remove(unit_number)
    else:
        selected.add(unit_number)

    selected_text = ", ".join(map(str, sorted(selected))) if selected else "None"
    await query.edit_message_text(
        f"Which {draft['subject_short_name']} units have you already completed?\n\n"
        f"Selected: {selected_text}\n\n"
        "Tap units to change the selection, then press Continue.",
        reply_markup=completed_units_keyboard(selected, draft["unit_numbers"]),
    )
    return RESCUE_COMPLETED


async def finish_completed_units(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query
    await query.answer()

    draft = context.user_data.get("rescue_draft")
    if not draft:
        await query.edit_message_text(
            "Your Exam Rescue session expired. Open /menu and start it again."
        )
        return ConversationHandler.END

    await query.edit_message_text(
        f"What score are you targeting in {draft['subject_short_name']}?\n\n"
        "Choose the minimum score Raven should plan for:",
        reply_markup=target_score_keyboard(),
    )
    return RESCUE_TARGET


async def generate_rescue_plan(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get("rescue_draft")

    if not draft:
        await query.edit_message_text(
            "Your Exam Rescue session expired. Open /menu and start it again."
        )
        return ConversationHandler.END

    target_score = int(query.data.rsplit(":", maxsplit=1)[1])
    plan = build_exam_rescue_plan(
        subject_code=draft["subject_code"],
        days=draft["days"],
        completed_units=draft["completed_units"],
        target_score=target_score,
    )
    plan_id = save_exam_rescue_plan(update.effective_chat.id, plan)
    preparation_level = infer_preparation_level(
        set(draft["completed_units"]),
        len(draft["unit_numbers"]),
    )
    save_subject_progress(
        chat_id=update.effective_chat.id,
        subject_code=draft["subject_code"],
        preparation_level=preparation_level,
        completed_units=draft["completed_units"],
    )
    context.user_data.pop("rescue_draft", None)

    await query.edit_message_text(
        f"✅ {plan['subject_short_name']} Exam Rescue plan #{plan_id} created."
    )
    await send_in_chunks(query.message, format_exam_rescue_plan(plan))
    await query.message.reply_text(
        "Return to Academics when you are ready:",
        reply_markup=back_to_academics_keyboard(),
    )
    return ConversationHandler.END


async def cancel_exam_rescue(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    context.user_data.pop("rescue_draft", None)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "Exam Rescue cancelled.",
            reply_markup=back_to_subjects_keyboard("exam_rescue"),
        )
    else:
        await update.effective_message.reply_text(
            "Exam Rescue cancelled. Open /menu whenever you want to try again."
        )

    return ConversationHandler.END


async def last_plan_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    plan = get_latest_exam_rescue_plan(update.effective_chat.id)

    if not plan:
        await update.effective_message.reply_text(
            "You do not have a saved Exam Rescue plan yet. "
            "Open /menu → Academics → Exam Rescue."
        )
        return

    await send_in_chunks(update.effective_message, format_exam_rescue_plan(plan))


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", maxsplit=1)[1]

    if action == "main":
        await query.edit_message_text(
            "🐦‍⬛ RAVEN — MAIN MENU",
            reply_markup=main_menu_keyboard(),
        )
        return

    if action == "academics":
        await query.edit_message_text(
            "📚 ACADEMICS\n\nChoose what you need:",
            reply_markup=academics_menu_keyboard(),
        )
        return

    if action in {"exam_rescue", "syllabus", "resources"}:
        profile = get_student_profile(update.effective_chat.id)
        if not profile:
            await query.edit_message_text(
                "You need a student profile first. Send /setup."
            )
            return

        subjects = list_subjects(
            profile["branch"],
            profile["semester"],
            feature=action,
        )
        if not subjects:
            await query.edit_message_text(
                "Raven does not have an Academic catalog for your branch and "
                "semester yet.",
                reply_markup=back_to_academics_keyboard(),
            )
            return

        section_titles = {
            "exam_rescue": "🚨 EXAM RESCUE",
            "syllabus": "📘 SYLLABUS",
            "resources": "📖 RESOURCES",
        }
        await query.edit_message_text(
            f"{section_titles[action]}\n\n"
            f"Semester {profile['semester']} • {profile['branch']}\n"
            "Choose a subject:",
            reply_markup=subject_picker_keyboard(action, subjects),
        )
        return

    if action == "profile":
        profile = get_student_profile(update.effective_chat.id)
        text = format_profile(profile) if profile else "Send /setup to create your profile."
        await query.edit_message_text(text, reply_markup=back_to_menu_keyboard())
        return

    if action == "chat":
        text = (
            "💬 CHAT\n\nAsk Raven normally. Academic syllabus, resources, credits "
            "and preparation data are retrieved before Ollama answers."
        )
    elif action == "attendance":
        text = "📊 Attendance tracking is planned after the Academic resource foundation."
    elif action == "updates":
        text = "📢 Verified JSS/AKTU notices and deadline alerts are planned for a later sprint."
    elif action == "projects":
        text = "🛠 Project planning will be built after the Academic MVP is tested."
    elif action == "growth":
        text = "🌱 Goals, tasks and habits will be added after Projects."
    elif action == "community":
        text = "🤝 Community matching will launch only after privacy controls and enough users exist."
    else:
        text = "That Raven feature is not available yet."

    academic_actions = {"attendance", "updates"}
    keyboard = (
        back_to_academics_keyboard()
        if action in academic_actions
        else back_to_menu_keyboard()
    )
    await query.edit_message_text(text, reply_markup=keyboard)


async def academic_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    await query.answer()
    _, feature, subject_code = query.data.split(":", maxsplit=2)
    subject_code = subject_code.upper()

    profile = get_student_profile(update.effective_chat.id)
    if not profile:
        await query.edit_message_text(
            "You need a student profile first. Send /setup."
        )
        return

    profile_subjects = {
        subject["subject_code"]: subject
        for subject in list_subjects(
            profile["branch"],
            profile["semester"],
            feature=feature,
        )
    }
    metadata = profile_subjects.get(subject_code)

    if not metadata:
        await query.edit_message_text(
            "That subject is not available for your current branch and semester.",
            reply_markup=back_to_subjects_keyboard(feature),
        )
        return

    if metadata["status"] != "available":
        await query.edit_message_text(
            f"🔒 {metadata['short_name']} is coming soon in this section.\n\n"
            "Choose one of the currently available subjects.",
            reply_markup=back_to_subjects_keyboard(feature),
        )
        return

    if feature == "syllabus":
        text = format_subject_syllabus(subject_code)
    elif feature == "resources":
        text = format_subject_resources(subject_code)
    else:
        text = "Open Exam Rescue again to start a plan."

    await query.edit_message_text(
        text,
        reply_markup=back_to_subjects_keyboard(feature),
    )


async def remember_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    memory_text = " ".join(context.args).strip()

    if not memory_text:
        await update.effective_message.reply_text(
            "Usage: /remember <something you want Raven to remember>"
        )
        return

    memory_id, status = save_memory(
        chat_id=update.effective_chat.id,
        content=memory_text,
        category="manual",
        importance=8,
    )

    if status == "exists":
        text = f"🧠 I already remember that. Memory ID: {memory_id}"
    else:
        text = f"🧠 Memory #{memory_id} {status}.\n\n{memory_text}"

    await update.effective_message.reply_text(text)


async def memories_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    memories = get_memories(update.effective_chat.id, limit=100)

    if not memories:
        await update.effective_message.reply_text(
            "🧠 I don't have any long-term memories yet."
        )
        return

    lines = ["🧠 RAVEN'S LONG-TERM MEMORY"]
    lines.extend(
        f"#{memory['id']} [{memory['category']}] {memory['content']}"
        for memory in memories
    )
    await send_in_chunks(update.effective_message, "\n\n".join(lines))


async def forget_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.effective_message.reply_text(
            "Usage: /forget <memory ID>\nUse /memories to see IDs."
        )
        return

    try:
        memory_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("⚠️ Memory ID must be a number.")
        return

    deleted = delete_memory(update.effective_chat.id, memory_id)
    text = (
        f"🗑️ Memory #{memory_id} forgotten."
        if deleted
        else f"⚠️ I couldn't find memory #{memory_id}."
    )
    await update.effective_message.reply_text(text)


async def forgetall_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or context.args[0].upper() != "CONFIRM":
        await update.effective_message.reply_text(
            "⚠️ This permanently deletes all long-term memories.\n\n"
            "To confirm, send: /forgetall CONFIRM"
        )
        return

    deleted_count = clear_memories(update.effective_chat.id)
    await update.effective_message.reply_text(
        f"🧠 Long-term memory cleared. {deleted_count} memories deleted."
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deleted_count = clear_chat_history(update.effective_chat.id)
    await update.effective_message.reply_text(
        f"🧹 Recent conversation history cleared ({deleted_count} messages).\n"
        "Your long-term memories, student profile and preparation progress "
        "were not deleted."
    )


def _progress_by_subject(chat_id: int) -> dict[str, dict]:
    return {
        progress["subject_code"]: progress
        for progress in get_all_subject_progress(chat_id)
    }


async def progress_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    chat_id = update.effective_chat.id
    profile = get_student_profile(chat_id)
    if not profile:
        await update.effective_message.reply_text(
            "You need a student profile first. Send /setup."
        )
        return

    subjects = list_subjects(profile["branch"], profile["semester"])

    if not subjects:
        subjects = list_all_subjects()

    requested_text = " ".join(context.args).strip()
    subject_code = (
        detect_subject_code(requested_text, subjects)
        if requested_text
        else None
    )
    if requested_text and not subject_code:
        await update.effective_message.reply_text(
            "I couldn't identify that subject. Try /progress COA or /progress DSTL."
        )
        return

    text = format_progress_summary(
        subjects,
        _progress_by_subject(chat_id),
        subject_code,
    )
    await send_in_chunks(update.effective_message, text)


def _apply_progress_update(
    *,
    chat_id: int,
    route: AcademicRoute,
) -> dict:
    subject = load_subject(route.subject_code)
    valid_units = {unit["number"] for unit in subject["units"]}
    requested_units = set(route.unit_numbers)
    if not requested_units.issubset(valid_units):
        valid_text = ", ".join(map(str, sorted(valid_units)))
        raise ValueError(f"Completed units can contain only: {valid_text}")

    existing = get_subject_progress(chat_id, route.subject_code) or {}
    completed = set(existing.get("completed_units", []))
    if route.completed_action == "add":
        completed.update(requested_units)
    elif route.completed_action == "remove":
        completed.difference_update(requested_units)

    level = route.preparation_level
    if level is None and route.completed_action:
        level = infer_preparation_level(completed, len(valid_units))

    return save_subject_progress(
        chat_id=chat_id,
        subject_code=route.subject_code,
        preparation_level=level,
        completed_units=completed,
        latest_score=route.latest_score,
        latest_score_max=route.latest_score_max,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_message = update.effective_message.text.strip()

    if not user_message:
        return

    logger.info("User chat_id=%s sent a message", chat_id)
    save_message(chat_id=chat_id, role="user", content=user_message)

    profile = get_student_profile(chat_id)

    subjects = (
        list_subjects(profile["branch"], profile["semester"])
        if profile
        else []
    )
    
    # If an older or unusual profile branch does not match the catalog,
    # still let Raven recognise explicitly requested subjects.
    if not subjects:
        subjects = list_all_subjects()
    
    route = route_academic_message(user_message, subjects)
    
    # Complete a request such as:
    # User: "Give me Unit 4 resources"
    # Raven: "Which subject?"
    # User: "COA"
    pending_request = context.user_data.get("pending_academic_request")
    
    if pending_request and any(
        phrase in user_message.casefold()
        for phrase in ("never mind", "nevermind", "cancel")
    ):
        context.user_data.pop("pending_academic_request", None)
    
        route = AcademicRoute(
            kind="direct",
            intent="cancel_pending",
            response="Okay—the pending academic request was cancelled.",
        )
    
        pending_request = None
    
    if pending_request and route.subject_code:
        units = " ".join(
            f"Unit {unit}"
            for unit in pending_request.get("unit_numbers", [])
        )
    
        route = route_academic_message(
            (
                f"{pending_request['intent']} "
                f"{units} {route.subject_code}"
            ),
            subjects,
        )
    
        context.user_data.pop("pending_academic_request", None)
        pending_request = None
    
    if pending_request and route.kind == "none":
        available = ", ".join(
            subject["short_name"] for subject in subjects
        )
    
        route = AcademicRoute(
            kind="direct",
            intent=pending_request["intent"],
            unit_numbers=tuple(
                pending_request.get("unit_numbers", [])
            ),
            response=(
                "I still couldn't match that subject. "
                f"Choose one of: {available}."
            ),
        )
    
    previous_subject = context.user_data.get(
        "last_academic_subject_code"
    )
    
    if (
        route.subject_code is None
        and previous_subject
        and looks_like_academic_followup(user_message)
    ):
        route = route_academic_message(
            f"{user_message} {previous_subject}",
            subjects,
        )
    
    if route.subject_code:
        context.user_data["last_academic_subject_code"] = (
            route.subject_code
        )
    
    elif (
        route.kind == "direct"
        and route.intent in {"resources", "syllabus"}
    ):
        context.user_data["pending_academic_request"] = {
            "intent": route.intent,
            "unit_numbers": list(route.unit_numbers),
    }
    if (
        route.subject_code is None
        and previous_subject
        and looks_like_academic_followup(user_message)
    ):
        route = route_academic_message(
            f"{user_message} {previous_subject}",
            subjects,
        )
    if route.subject_code:
        context.user_data["last_academic_subject_code"] = route.subject_code

    if route.kind == "direct":
        reply = route.response or "I couldn't retrieve that academic information."
        save_message(chat_id=chat_id, role="assistant", content=reply)
        await send_in_chunks(update.effective_message, reply)
        return

    if route.kind == "progress_view":
        reply = format_progress_summary(
            subjects,
            _progress_by_subject(chat_id),
            route.subject_code,
        )
        save_message(chat_id=chat_id, role="assistant", content=reply)
        await send_in_chunks(update.effective_message, reply)
        return

    if route.kind == "progress_update":
        try:
            saved_progress = _apply_progress_update(chat_id=chat_id, route=route)
            reply = "✅ Preparation progress updated.\n\n" + format_progress_summary(
                subjects,
                {route.subject_code: saved_progress},
                route.subject_code,
            )
        except ValueError as error:
            reply = f"⚠️ {error}"
        save_message(chat_id=chat_id, role="assistant", content=reply)
        await send_in_chunks(update.effective_message, reply)
        return

    recent_history = get_recent_messages(
        chat_id=chat_id,
        limit=RECENT_MESSAGE_LIMIT,
    )
    long_term_memories = get_memories(
        chat_id=chat_id,
        limit=LONG_TERM_MEMORY_LIMIT,
    )
    complete_system_prompt = SYSTEM_PROMPT + build_memory_context(long_term_memories)
    if route.kind == "context":
        academic_context = build_academic_context(
            route,
            get_subject_progress(chat_id, route.subject_code),
        )
        complete_system_prompt += "\n\n" + academic_context
    messages = [{"role": "system", "content": complete_system_prompt}]
    messages.extend(recent_history)

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        ai_reply = await asyncio.to_thread(ask_ollama, messages)
        save_message(chat_id=chat_id, role="assistant", content=ai_reply)
        await send_in_chunks(update.effective_message, ai_reply)
    except requests.exceptions.ConnectionError:
        await update.effective_message.reply_text(
            "⚠️ I can't connect to Ollama. Make sure Ollama is running."
        )
    except requests.exceptions.Timeout:
        await update.effective_message.reply_text(
            "⏳ The local AI took too long to respond."
        )
    except Exception:
        logger.exception("Message handling failed for chat_id=%s", chat_id)
        await update.effective_message.reply_text(
            "⚠️ Something went wrong while processing your message."
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled Telegram error", exc_info=context.error)


def build_application() -> Application:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    onboarding = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_command),
            CommandHandler("setup", setup_command),
        ],
        states={
            PROFILE_COLLEGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_college)
            ],
            PROFILE_BRANCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_branch)
            ],
            PROFILE_YEAR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_year)
            ],
            PROFILE_SEMESTER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_semester)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_onboarding)],
        allow_reentry=True,
    )

    exam_rescue = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                start_exam_rescue,
                pattern=r"^academic:exam_rescue:[A-Z0-9]+$",
            )
        ],
        states={
            RESCUE_DAYS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_rescue_days)
            ],
            RESCUE_COMPLETED: [
                CallbackQueryHandler(
                    toggle_completed_unit,
                    pattern=r"^rescue:unit:\d+$",
                ),
                CallbackQueryHandler(
                    finish_completed_units,
                    pattern=r"^rescue:units_done$",
                ),
            ],
            RESCUE_TARGET: [
                CallbackQueryHandler(
                    generate_rescue_plan,
                    pattern=r"^rescue:target:(40|50|60|70)$",
                )
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_exam_rescue),
            CallbackQueryHandler(
                cancel_exam_rescue,
                pattern=r"^rescue:cancel$",
            ),
        ],
        allow_reentry=True,
    )

    application.add_handler(onboarding)
    application.add_handler(exam_rescue)
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("lastplan", last_plan_command))
    application.add_handler(CommandHandler("progress", progress_command))
    application.add_handler(CommandHandler("remember", remember_command))
    application.add_handler(CommandHandler("memories", memories_command))
    application.add_handler(CommandHandler("forget", forget_command))
    application.add_handler(CommandHandler("forgetall", forgetall_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(
        CallbackQueryHandler(
            academic_callback,
            pattern=r"^academic:(syllabus|resources):[A-Z0-9]+$",
        )
    )
    application.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu:"))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    application.add_error_handler(error_handler)
    return application


def main() -> None:
    validate_settings()
    init_db()
    application = build_application()

    logger.info("Raven Sprint 2.4 is online")
    logger.info("Ollama model: %s", OLLAMA_MODEL)
    logger.info("Database initialized")
    application.run_polling()


if __name__ == "__main__":
    main()
