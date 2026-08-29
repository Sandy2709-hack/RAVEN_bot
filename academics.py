import json
import math
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SUBJECTS_CATALOG_PATH = DATA_DIR / "subjects.json"


def _validate_subject_catalog(catalog: dict[str, Any]) -> None:
    if not isinstance(catalog.get("groups"), list):
        raise ValueError("Subject catalog must contain a groups list")

    for group in catalog["groups"]:
        if not isinstance(group.get("subjects"), list):
            raise ValueError("Every catalog group must contain a subjects list")

        seen_codes: set[str] = set()
        for subject in group["subjects"]:
            subject_code = str(subject.get("subject_code", "")).strip().upper()
            if not subject_code:
                raise ValueError("Every subject must have a subject_code")
            if subject_code in seen_codes:
                raise ValueError(f"Duplicate subject code in catalog: {subject_code}")
            seen_codes.add(subject_code)

            credits = subject.get("credits")
            if isinstance(credits, bool) or not isinstance(credits, int):
                raise ValueError(
                    f"Credits for {subject_code} must be stored as a JSON integer"
                )
            if credits not in range(1, 11):
                raise ValueError(f"Credits for {subject_code} must be between 1 and 10")


def load_subject_catalog() -> dict[str, Any]:
    with SUBJECTS_CATALOG_PATH.open("r", encoding="utf-8") as file:
        catalog = json.load(file)

    _validate_subject_catalog(catalog)
    return catalog


def _normalise_label(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def list_subjects(
    branch: str,
    semester: int,
    feature: str | None = None,
) -> list[dict[str, Any]]:
    """Return the catalog subjects that match a student's profile."""
    normalised_branch = _normalise_label(branch)
    matches = []

    for group in load_subject_catalog()["groups"]:
        aliases = {_normalise_label(alias) for alias in group["branch_aliases"]}
        if group["semester"] != semester or normalised_branch not in aliases:
            continue

        for subject in group["subjects"]:
            if feature and feature not in subject.get("features", []):
                continue
            item = dict(subject)
            item["semester"] = group["semester"]
            item["branch_group"] = group["branch_group"]
            matches.append(item)

    matches.sort(
        key=lambda subject: (
            subject["status"] != "available",
            subject.get("display_order", 999),
            subject["subject_code"],
        )
    )
    return matches


def list_all_subjects(
    feature: str | None = None,
    available_only: bool = True,
) -> list[dict[str, Any]]:
    """Return unique catalog subjects independently of a student's profile."""
    matches: dict[str, dict[str, Any]] = {}
    for group in load_subject_catalog()["groups"]:
        for subject in group["subjects"]:
            if feature and feature not in subject.get("features", []):
                continue
            if available_only and subject["status"] != "available":
                continue
            code = subject["subject_code"].upper()
            if code in matches:
                continue
            item = dict(subject)
            item["semester"] = group["semester"]
            item["branch_group"] = group["branch_group"]
            matches[code] = item

    return sorted(
        matches.values(),
        key=lambda subject: (
            subject["status"] != "available",
            subject.get("semester", 99),
            subject.get("display_order", 999),
            subject["subject_code"],
        ),
    )


def get_subject_metadata(subject_code: str) -> dict[str, Any] | None:
    wanted_code = subject_code.strip().upper()

    for group in load_subject_catalog()["groups"]:
        for subject in group["subjects"]:
            if subject["subject_code"].upper() == wanted_code:
                item = dict(subject)
                item["semester"] = group["semester"]
                item["branch_group"] = group["branch_group"]
                return item

    return None


def load_subject(subject_code: str) -> dict[str, Any]:
    metadata = get_subject_metadata(subject_code)
    if not metadata:
        raise ValueError(f"Unknown subject code: {subject_code}")
    if metadata["status"] != "available" or not metadata.get("data_file"):
        raise ValueError(f"Subject {metadata['subject_code']} is not available yet")

    data_path = (DATA_DIR / metadata["data_file"]).resolve()
    if DATA_DIR.resolve() not in data_path.parents:
        raise ValueError("Subject data path must stay inside the data directory")

    with data_path.open("r", encoding="utf-8") as file:
        subject = json.load(file)

    subject["short_name"] = metadata["short_name"]
    subject["status"] = metadata["status"]
    subject["credits"] = metadata["credits"]
    return subject


def load_coa_subject() -> dict[str, Any]:
    """Backward-compatible helper for existing COA imports."""
    return load_subject("BCS302")


def _distribute_minutes(total: int, weights: list[float]) -> list[int]:
    if total <= 0 or not weights:
        return [0 for _ in weights]

    weight_sum = sum(weights)
    raw = [(total * weight) / weight_sum for weight in weights]
    allocated = [math.floor(value) for value in raw]
    remaining = total - sum(allocated)

    fractional_order = sorted(
        range(len(raw)),
        key=lambda index: raw[index] - allocated[index],
        reverse=True,
    )

    for index in fractional_order[:remaining]:
        allocated[index] += 1

    return allocated


def _topic_summary(topics: list[str], maximum: int = 3) -> str:
    selected = topics[:maximum]
    summary = "; ".join(selected)

    if len(topics) > maximum:
        summary += f"; +{len(topics) - maximum} more syllabus topics"

    return summary


def _automatic_daily_minutes(days: int, target_score: int) -> int:
    """Choose a practical rescue workload without asking for study hours."""
    if days == 1:
        base_minutes = 300
    elif days <= 3:
        base_minutes = 240
    elif days <= 7:
        base_minutes = 180
    elif days <= 14:
        base_minutes = 120
    else:
        base_minutes = 90

    target_adjustment = {
        40: -30,
        50: 0,
        60: 30,
        70: 60,
    }[target_score]
    return max(60, base_minutes + target_adjustment)


def _rescue_pace_label(days: int) -> str:
    if days == 1:
        return "Last-day rescue"
    if days <= 3:
        return "Emergency sprint"
    if days <= 7:
        return "Focused sprint"
    if days <= 14:
        return "Steady preparation"
    return "Comfortable preparation"


def build_exam_rescue_plan(
    *,
    subject_code: str,
    days: int,
    completed_units: set[int] | list[int],
    target_score: int,
) -> dict[str, Any]:
    if days not in range(1, 31):
        raise ValueError("days must be between 1 and 30")

    if target_score not in {40, 50, 60, 70}:
        raise ValueError("target_score must be 40, 50, 60, or 70")

    subject = load_subject(subject_code)
    units = subject["units"]
    valid_unit_numbers = {unit["number"] for unit in units}
    completed = {int(unit) for unit in completed_units}
    if not completed.issubset(valid_unit_numbers):
        valid_text = ", ".join(map(str, sorted(valid_unit_numbers)))
        raise ValueError(f"completed_units can contain only: {valid_text}")

    daily_capacity = _automatic_daily_minutes(days, target_score)
    total_minutes = daily_capacity * days

    revision_ratio = {
        40: 0.16,
        50: 0.18,
        60: 0.21,
        70: 0.24,
    }[target_score]
    revision_minutes = max(15, round(total_minutes * revision_ratio))
    revision_minutes = min(revision_minutes, max(15, daily_capacity - 10))
    learning_minutes = max(0, total_minutes - revision_minutes)

    # Completed units receive review time, but unfinished units receive most of
    # the schedule. For extremely small time budgets, a few meaningful blocks
    # are safer than pretending three minutes is enough for every unit. These
    # are coverage weights, not unverified PYQ weights.
    minimum_unit_block = 15
    maximum_covered_units = max(1, learning_minutes // minimum_unit_block)
    maximum_covered_units = min(len(units), maximum_covered_units)
    ranked_indexes = sorted(
        range(len(units)),
        key=lambda index: (
            units[index]["number"] not in completed,
            units[index]["planning_weight"],
            -units[index]["number"],
        ),
        reverse=True,
    )
    selected_indexes = set(ranked_indexes[:maximum_covered_units])
    weights = [
        (
            unit["planning_weight"]
            * (0.3 if unit["number"] in completed else 1.0)
        )
        if index in selected_indexes
        else 0.0
        for index, unit in enumerate(units)
    ]
    allocations = _distribute_minutes(learning_minutes, weights)

    day_capacities = [daily_capacity for _ in range(days)]
    day_capacities[-1] -= revision_minutes
    day_plans = [
        {"day": day + 1, "allocated_minutes": 0, "items": []}
        for day in range(days)
    ]

    current_day = 0
    covered_units = []
    minimal_units = []
    omitted_units = []

    for unit, allocated_minutes in zip(units, allocations):
        if allocated_minutes <= 0:
            omitted_units.append(unit["number"])
            continue

        covered_units.append(unit["number"])
        if allocated_minutes < 20:
            minimal_units.append(unit["number"])

        remaining = allocated_minutes
        first_block = True

        while remaining > 0 and current_day < days:
            available = day_capacities[current_day]

            if available <= 0:
                current_day += 1
                continue

            block_minutes = min(remaining, available, 90)
            resources = unit.get("resources") or []
            resource = resources[0] if resources else {}
            status = "Review" if unit["number"] in completed else "Study"
            action = (
                f"{status} Unit {unit['number']}: {unit['title']}"
                if first_block
                else f"Continue Unit {unit['number']} + active recall"
            )

            item = {
                "type": "unit_study",
                "unit": unit["number"],
                "title": action,
                "minutes": block_minutes,
                "topics": _topic_summary(unit["topics"]),
                "resource_title": resource.get("title"),
                "resource_url": resource.get("url"),
            }
            day_plans[current_day]["items"].append(item)
            day_plans[current_day]["allocated_minutes"] += block_minutes
            day_capacities[current_day] -= block_minutes
            remaining -= block_minutes
            first_block = False

            if day_capacities[current_day] <= 0:
                current_day += 1

    final_day = day_plans[-1]
    final_day["items"].append(
        {
            "type": "final_revision",
            "title": "Final recall and available question practice",
            "minutes": revision_minutes,
            "topics": (
                "Revise formulas, diagrams, definitions and weak topics. "
                f"Solve any available {subject['short_name']} questions without notes."
            ),
        }
    )
    final_day["allocated_minutes"] += revision_minutes

    depth = {
        40: "pass-focused syllabus coverage",
        50: "balanced coverage and revision",
        60: "strong conceptual coverage and practice",
        70: "deep coverage with additional recall time",
    }[target_score]

    return {
        "version": 3,
        "subject_code": subject["subject_code"],
        "subject_name": subject["subject_name"],
        "subject_short_name": subject["short_name"],
        "credits": subject["credits"],
        "days": days,
        "daily_minutes": daily_capacity,
        "pace_label": _rescue_pace_label(days),
        "target_score": target_score,
        "completed_units": sorted(completed),
        "total_minutes": total_minutes,
        "revision_minutes": revision_minutes,
        "strategy": depth,
        "ranking_status": subject["resource_status"],
        "covered_units": covered_units,
        "minimal_units": minimal_units,
        "omitted_units": omitted_units,
        "days_plan": day_plans,
        "syllabus_source": subject["syllabus_source"],
    }


def format_exam_rescue_plan(plan: dict[str, Any]) -> str:
    completed = plan.get("completed_units") or []
    completed_text = ", ".join(map(str, completed)) if completed else "None"
    short_name = plan.get("subject_short_name")
    if not short_name:
        short_name = "COA" if plan.get("subject_code") == "BCS302" else plan["subject_code"]

    lines = [
        f"🚨 {short_name} EXAM RESCUE PLAN",
        "",
        f"Duration: {plan['days']} day(s)",
        f"Raven pace: {plan.get('pace_label', _rescue_pace_label(plan['days']))}",
        f"Target: {plan['target_score']}+ marks",
        f"Credits: {plan.get('credits', 'Not recorded')}",
        f"Completed units: {completed_text}",
        f"Strategy: {plan['strategy']}",
        "",
        "⚠️ Ranking status: syllabus-based, not yet PYQ-verified.",
    ]

    if plan.get("minimal_units"):
        units = ", ".join(map(str, plan["minimal_units"]))
        lines.extend(
            [
                "",
                f"Time warning: Unit(s) {units} receive only minimal coverage. "
                "Raven kept them to quick recall because the rescue window is tight.",
            ]
        )

    if plan.get("omitted_units"):
        units = ", ".join(map(str, plan["omitted_units"]))
        lines.extend(
            [
                "",
                f"Insufficient-time warning: Unit(s) {units} could not receive a "
                "meaningful study block. This is a coverage heuristic, not a claim "
                "that those units are unimportant.",
            ]
        )

    for day in plan["days_plan"]:
        lines.extend(
            [
                "",
                f"DAY {day['day']} — {day['allocated_minutes']} minutes",
            ]
        )

        for item in day["items"]:
            lines.append(f"• {item['title']} ({item['minutes']} min)")
            lines.append(f"  Focus: {item['topics']}")

            if item.get("resource_url"):
                lines.append(f"  Resource: {item['resource_url']}")

    lines.extend(
        [
            "",
            "Official syllabus:",
            plan["syllabus_source"],
            "",
            "Use /lastplan to open this plan again.",
        ]
    )
    return "\n".join(lines)


def format_subject_syllabus(subject_code: str) -> str:
    subject = load_subject(subject_code)
    lines = [
        f"📘 {subject['subject_code']} — {subject['subject_name']}",
        f"Credits: {subject['credits']}",
        "Official AKTU syllabus",
    ]

    for unit in subject["units"]:
        lines.extend(["", f"UNIT {unit['number']} — {unit['title']}"])
        lines.extend(f"• {topic}" for topic in unit["topics"])

    lines.extend(["", f"Source: {subject['syllabus_source']}"])
    return "\n".join(lines)


def format_subject_resources(subject_code: str) -> str:
    subject = load_subject(subject_code)
    lines = [
        f"📖 {subject['short_name']} VERIFIED STARTER RESOURCES",
        f"Credits: {subject['credits']}",
        "",
        "Free resources matched to the official syllabus",
    ]

    for unit in subject["units"]:
        resources = unit.get("resources") or []
        if not resources:
            continue
        resource = resources[0]
        search_query = quote_plus(
            f"{resource['provider']} {subject['short_name']} "
            f"Unit {unit['number']} {unit['title']}"
        )
        lines.extend(
            [
                "",
                f"Unit {unit['number']} — {unit['title']}",
                f"Provider: {resource['provider']}",
                f"Direct: {resource['url']}",
                "Search fallback: "
                f"https://www.youtube.com/results?search_query={search_query}",
            ]
        )

    lines.extend(
        [
            "",
            "These resources are matched to the official syllabus. "
            "They are not yet ranked using verified PYQ frequency.",
        ]
    )
    return "\n".join(lines)


def get_subject_unit(subject_code: str, unit_number: int) -> dict[str, Any]:
    subject = load_subject(subject_code)
    for unit in subject["units"]:
        if unit["number"] == int(unit_number):
            return unit
    raise ValueError(
        f"{subject['subject_code']} has no Unit {unit_number}; "
        f"choose Unit 1 to {len(subject['units'])}"
    )


def format_unit_syllabus(subject_code: str, unit_number: int) -> str:
    subject = load_subject(subject_code)
    unit = get_subject_unit(subject_code, unit_number)
    lines = [
        f"📘 {subject['short_name']} — UNIT {unit['number']}",
        f"{unit['title']}",
        f"Subject code: {subject['subject_code']}",
        f"Credits: {subject['credits']}",
        "",
        "Official syllabus topics:",
    ]
    lines.extend(f"• {topic}" for topic in unit["topics"])
    lines.extend(["", f"Source: {subject['syllabus_source']}"])
    return "\n".join(lines)


def format_unit_resources(subject_code: str, unit_number: int) -> str:
    subject = load_subject(subject_code)
    unit = get_subject_unit(subject_code, unit_number)
    resources = unit.get("resources") or []
    lines = [
        f"📖 {subject['short_name']} — UNIT {unit['number']} RESOURCES",
        f"{unit['title']}",
        f"Subject code: {subject['subject_code']}",
        f"Credits: {subject['credits']}",
        "",
    ]

    if not resources:
        lines.append("No verified starter resource is stored for this unit yet.")
    else:
        for resource in resources:
            search_query = quote_plus(
                f"{resource['provider']} {subject['short_name']} "
                f"Unit {unit['number']} {unit['title']}"
            )
            lines.extend(
                [
                    f"{resource['provider']} — {resource['title']}",
                    "Direct link:",
                    resource["url"],
                    "YouTube search fallback:",
                    f"https://www.youtube.com/results?search_query={search_query}",
                    "",
                ]
            )

    lines.append(
        "Syllabus-matched resource; ranking is not yet PYQ-verified."
    )
    return "\n".join(lines).strip()


def format_subject_credits(subject_code: str) -> str:
    subject = load_subject(subject_code)
    return (
        f"🎓 {subject['short_name']} ({subject['subject_code']}) carries "
        f"{subject['credits']} credit(s)."
    )


def format_coa_syllabus() -> str:
    """Backward-compatible wrapper for older code and tests."""
    return format_subject_syllabus("BCS302")


def format_coa_resources() -> str:
    """Backward-compatible wrapper for older code and tests."""
    return format_subject_resources("BCS302")
