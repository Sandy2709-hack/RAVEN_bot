import json
import math
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


BASE_DIR = Path(__file__).resolve().parent
TIMETABLES_DIR = BASE_DIR / "data" / "timetables"
RAVEN_TIMEZONE = ZoneInfo("Asia/Kolkata")


def _normalise(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def india_now() -> datetime:
    return datetime.now(RAVEN_TIMEZONE)


def india_today() -> date:
    return india_now().date()


def _validate_timetable(timetable: dict[str, Any]) -> None:
    required = {
        "college_id",
        "college_name",
        "branch",
        "branch_aliases",
        "semester",
        "periods",
        "subjects",
        "sections",
    }
    missing = required - set(timetable)
    if missing:
        raise ValueError(
            "Timetable is missing required values: " + ", ".join(sorted(missing))
        )

    seen_entry_ids: set[str] = set()
    for section_name, section in timetable["sections"].items():
        if not section.get("schedule"):
            raise ValueError(f"{section_name} must contain a schedule")
        for entries in section["schedule"].values():
            for entry in entries:
                entry_id = entry.get("id")
                if not entry_id or entry_id in seen_entry_ids:
                    raise ValueError(f"Invalid or duplicate timetable entry ID: {entry_id}")
                seen_entry_ids.add(entry_id)
                if entry.get("subject_code") not in timetable["subjects"]:
                    raise ValueError(
                        f"Unknown subject in timetable entry {entry_id}: "
                        f"{entry.get('subject_code')}"
                    )


def load_matching_timetable(profile: dict[str, Any]) -> dict[str, Any] | None:
    """Return a timetable directly matched to college, branch and semester."""
    college = _normalise(str(profile.get("college", "")))
    branch = _normalise(str(profile.get("branch", "")))
    semester = int(profile.get("semester", 0))

    for path in sorted(TIMETABLES_DIR.glob("**/*.json")):
        with path.open("r", encoding="utf-8") as file:
            timetable = json.load(file)
        _validate_timetable(timetable)

        college_labels = {
            _normalise(timetable["college_id"]),
            _normalise(timetable["college_name"]),
        }
        branch_labels = {
            _normalise(timetable["branch"]),
            *(_normalise(alias) for alias in timetable["branch_aliases"]),
        }
        college_matches = any(label and label in college for label in college_labels)
        if college_matches and branch in branch_labels and semester == timetable["semester"]:
            timetable["_path"] = str(path)
            return timetable

    return None


def available_sections(timetable: dict[str, Any]) -> list[str]:
    return list(timetable["sections"])


def available_batch_groups(
    timetable: dict[str, Any],
    section: str,
) -> list[str]:
    section_data = timetable["sections"].get(section.upper())
    return list(section_data.get("batch_groups", [])) if section_data else []


def _entry_applies_to_batch(entry: dict[str, Any], batch_group: str) -> bool:
    required_batch = entry.get("batch_group")
    return required_batch is None or required_batch.upper() == batch_group.upper()


def list_attendance_subjects(
    timetable: dict[str, Any],
    section: str,
    batch_group: str,
) -> list[dict[str, Any]]:
    section_data = timetable["sections"].get(section.upper())
    if not section_data:
        return []

    subject_codes: list[str] = []
    for entries in section_data["schedule"].values():
        for entry in entries:
            code = entry["subject_code"]
            metadata = timetable["subjects"][code]
            if (
                metadata.get("track_attendance", True)
                and _entry_applies_to_batch(entry, batch_group)
                and code not in subject_codes
            ):
                subject_codes.append(code)

    return [
        {"subject_code": code, **timetable["subjects"][code]}
        for code in subject_codes
    ]


def schedule_for_date(
    timetable: dict[str, Any],
    section: str,
    batch_group: str,
    class_date: date,
    *,
    attendance_only: bool = True,
) -> list[dict[str, Any]]:
    section_data = timetable["sections"].get(section.upper())
    if not section_data:
        return []

    day_name = class_date.strftime("%A").casefold()
    entries = section_data["schedule"].get(day_name, [])
    result = []

    for original in entries:
        if not _entry_applies_to_batch(original, batch_group):
            continue

        subject = timetable["subjects"][original["subject_code"]]
        if attendance_only and not subject.get("track_attendance", True):
            continue

        entry = dict(original)
        entry["subject"] = dict(subject)
        entry["class_count"] = len(entry["periods"])
        first_period = str(entry["periods"][0])
        last_period = str(entry["periods"][-1])
        start = timetable["periods"][first_period]["start"]
        end = timetable["periods"][last_period]["end"]
        entry["time_label"] = f"{start}-{end}"
        entry["period_label"] = (
            f"P{first_period}"
            if first_period == last_period
            else f"P{first_period}-P{last_period}"
        )
        result.append(entry)

    return result


def find_schedule_entry(
    timetable: dict[str, Any],
    section: str,
    batch_group: str,
    class_date: date,
    entry_id: str,
) -> dict[str, Any] | None:
    return next(
        (
            entry
            for entry in schedule_for_date(
                timetable,
                section,
                batch_group,
                class_date,
            )
            if entry["id"] == entry_id
        ),
        None,
    )


def match_subject(
    query: str,
    subjects: list[dict[str, Any]],
) -> dict[str, Any] | None:
    wanted = _normalise(query)
    if not wanted:
        return None

    exact_matches = []
    contained_matches = []
    query_text = query.casefold()

    for subject in subjects:
        labels = {
            subject["subject_code"],
            subject["name"],
            subject["short_name"],
            *subject.get("aliases", []),
        }
        normalised_labels = {_normalise(label) for label in labels}
        if wanted in normalised_labels:
            exact_matches.append(subject)
            continue

        for label in labels:
            if len(label) > 2 and re.search(
                rf"(?<!\w){re.escape(label.casefold())}(?!\w)",
                query_text,
            ):
                contained_matches.append(subject)
                break

    matches = exact_matches or contained_matches
    return matches[0] if len(matches) == 1 else None


def calculate_attendance(
    attended: int,
    absent: int,
    *,
    target_percentage: float = 75.0,
) -> dict[str, Any]:
    attended = max(0, int(attended))
    absent = max(0, int(absent))
    target_percentage = float(target_percentage)
    if not 1 <= target_percentage < 100:
        raise ValueError("target_percentage must be between 1 and 99.99")

    total = attended + absent
    percentage = (attended / total * 100) if total else None
    target = target_percentage / 100

    if not total:
        safe_misses = 0
        required_attends = 0
    else:
        safe_misses = max(0, math.floor((attended / target) - total + 1e-9))
        required_attends = max(
            0,
            math.ceil(((target * total) - attended) / (1 - target) - 1e-9),
        )

    if percentage is None:
        level = "not_recorded"
        emoji = "⚪"
        label = "No classes recorded"
    elif percentage >= 85:
        level = "excellent"
        emoji = "🟢"
        label = "Excellent"
    elif percentage >= 75:
        level = "safe"
        emoji = "🟡"
        label = "Safe - maintain it"
    elif percentage >= 60:
        level = "danger"
        emoji = "🟠"
        label = "Danger - recovery required"
    else:
        level = "critical"
        emoji = "🔴"
        label = "Critical"

    return {
        "attended": attended,
        "absent": absent,
        "conducted": total,
        "percentage": percentage,
        "level": level,
        "emoji": emoji,
        "label": label,
        "target_percentage": target_percentage,
        "safe_misses": safe_misses,
        "required_attends": required_attends,
    }


def parse_calendar_date(value: str) -> date:
    value = value.strip()
    for date_format in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    raise ValueError("Use DD-MM-YYYY, for example 15-09-2026")


def parse_cia_dates(value: str) -> list[date]:
    values = [item.strip() for item in value.split(",") if item.strip()]
    if not values:
        return []
    dates = sorted({parse_calendar_date(item) for item in values})
    return dates


def next_cia_date(cia_dates: list[str], today: date | None = None) -> date | None:
    today = today or india_today()
    parsed = sorted(date.fromisoformat(item) for item in cia_dates)
    return next((cia_date for cia_date in parsed if cia_date >= today), None)


def format_attendance_dashboard(
    totals: list[dict[str, Any]],
    *,
    section: str,
    batch_group: str,
    target_percentage: float,
    cia_dates: list[str] | None = None,
    today: date | None = None,
) -> str:
    calculated = [
        (
            item,
            calculate_attendance(
                item["attended"],
                item["absent"],
                target_percentage=target_percentage,
            ),
        )
        for item in totals
    ]
    recorded = [stats for _, stats in calculated if stats["percentage"] is not None]
    cia_eligible = sum(
        stats["percentage"] >= target_percentage
        for stats in recorded
    )
    lines = [
        "📊 ATTENDANCE DASHBOARD",
        "",
        f"Section: {section} • Batch: {batch_group}",
        f"Safety target: {target_percentage:g}%",
        f"CIA readiness today: {cia_eligible}/{len(recorded)} recorded subjects safe",
    ]
    upcoming_cia = next_cia_date(cia_dates or [], today)
    if upcoming_cia:
        lines.append(f"Next CIA: {upcoming_cia.strftime('%d %b %Y')}")

    lines.append("")
    lines.extend(["", "SEMESTER-TO-DATE"])
    for item, stats in calculated:
        estimate = " ~estimated" if item.get("estimated") else ""
        if stats["percentage"] is None:
            percentage_text = "not recorded"
        else:
            percentage_text = f"{stats['percentage']:.2f}%{estimate}"
        lines.extend(
            [
                f"{stats['emoji']} {item['short_name']} - {percentage_text}",
                f"   {stats['attended']}/{stats['conducted']} attended • "
                f"safe bunks: {stats['safe_misses']} • "
                f"need for target: {stats['required_attends']}",
            ]
        )

    if not totals:
        lines.append("No active attendance subjects. Run /attendance setup.")

    return "\n".join(lines)
