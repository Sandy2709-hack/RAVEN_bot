import json
import math
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
COA_DATA_PATH = DATA_DIR / "coa_bcs302.json"


def load_coa_subject() -> dict[str, Any]:
    with COA_DATA_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


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


def build_exam_rescue_plan(
    *,
    days: int,
    hours_per_day: float,
    completed_units: set[int] | list[int],
    target_score: int,
) -> dict[str, Any]:
    if days not in range(1, 31):
        raise ValueError("days must be between 1 and 30")

    if not 0.5 <= hours_per_day <= 12:
        raise ValueError("hours_per_day must be between 0.5 and 12")

    if target_score not in {40, 50, 60, 70}:
        raise ValueError("target_score must be 40, 50, 60, or 70")

    completed = {int(unit) for unit in completed_units}
    if not completed.issubset({1, 2, 3, 4, 5}):
        raise ValueError("completed_units can contain only unit numbers 1-5")

    subject = load_coa_subject()
    units = subject["units"]
    daily_capacity = max(30, round(hours_per_day * 60))
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
            resource = unit["resources"][0]
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
                "resource_title": resource["title"],
                "resource_url": resource["url"],
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
                "Revise formulas, diagrams, instruction cycles, cache mappings, "
                "DMA and weak topics. Solve any available COA questions without notes."
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
        "version": 1,
        "subject_code": subject["subject_code"],
        "subject_name": subject["subject_name"],
        "days": days,
        "hours_per_day": hours_per_day,
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

    lines = [
        "🚨 COA EXAM RESCUE PLAN",
        "",
        f"Duration: {plan['days']} day(s)",
        f"Daily study time: {plan['hours_per_day']:g} hour(s)",
        f"Target: {plan['target_score']}+ marks",
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
                "Increase your daily hours if possible.",
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


def format_coa_syllabus() -> str:
    subject = load_coa_subject()
    lines = [
        f"📘 {subject['subject_code']} — {subject['subject_name']}",
        "Official AKTU syllabus",
    ]

    for unit in subject["units"]:
        lines.extend(["", f"UNIT {unit['number']} — {unit['title']}"])
        lines.extend(f"• {topic}" for topic in unit["topics"])

    lines.extend(["", f"Source: {subject['syllabus_source']}"])
    return "\n".join(lines)


def format_coa_resources() -> str:
    subject = load_coa_subject()
    lines = [
        "📖 COA VERIFIED STARTER RESOURCES",
        "",
        "Provider: Gateway Classes",
        "Access: Free YouTube videos",
    ]

    for unit in subject["units"]:
        resource = unit["resources"][0]
        lines.extend(
            [
                "",
                f"Unit {unit['number']} — {unit['title']}",
                resource["url"],
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
