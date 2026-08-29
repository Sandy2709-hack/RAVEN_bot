import re
from dataclasses import dataclass
from typing import Any

from academics import (
    format_subject_credits,
    format_subject_resources,
    format_subject_syllabus,
    format_unit_resources,
    format_unit_syllabus,
    get_subject_unit,
    load_subject,
)


PREPARATION_LEVEL_LABELS = {
    "not_started": "Not started",
    "basics_completed": "Basics completed",
    "mostly_prepared": "Mostly prepared",
    "revision_only": "Revision only",
}

SUBJECT_ALIASES = {
    "BCS301": {
        "data structure",
        "data structures",
        "ds",
        "dsa",
    },
    "BCS302": {
        "coa",
        "computer organization",
        "computer organisation",
        "computer architecture",
        "computer organization and architecture",
    },
    "BAS301": {
        "technical communication",
        "tech communication",
        "technical comm",
        "tc",
    },
    "BCC301": {
        "cyber security",
        "cybersecurity",
    },
    "BCS303": {
        "dstl",
        "discrete structures",
        "discrete structure",
        "theory of logic",
        "discrete structures and theory of logic",
    },
}

RESOURCE_WORDS = {
    "resource",
    "resources",
    "video",
    "videos",
    "lecture",
    "lectures",
    "youtube",
    "link",
    "links",
    "notes",
}
SYLLABUS_WORDS = {
    "syllabus",
    "topic",
    "topics",
    "chapter",
    "chapters",
    "curriculum",
    "contents",
}
CONTEXT_WORDS = {
    "explain",
    "teach",
    "understand",
    "study",
    "revise",
    "prepare",
    "learn",
    "question",
    "questions",
    "next",
    "help",
}


@dataclass(frozen=True)
class AcademicRoute:
    kind: str
    intent: str | None = None
    subject_code: str | None = None
    unit_numbers: tuple[int, ...] = ()
    response: str | None = None
    context: str | None = None
    completed_action: str | None = None
    preparation_level: str | None = None
    latest_score: float | None = None
    latest_score_max: float | None = None


def _normalise_text(value: str) -> str:
    value = value.casefold().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def looks_like_academic_followup(message: str) -> bool:
    normalised = _normalise_text(message)
    words = set(normalised.split())
    return (
        bool(re.search(r"\bunits?\s*\d+\b", normalised))
        or bool(words & RESOURCE_WORDS)
        or bool(words & SYLLABUS_WORDS)
        or bool(words & CONTEXT_WORDS)
        or "credit" in words
        or "credits" in words
        or "progress" in words
        or _contains_phrase(normalised, "preparation status")
    )


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text) is not None


def detect_subject_code(
    message: str,
    subjects: list[dict[str, Any]],
) -> str | None:
    normalised = _normalise_text(message)
    candidates: list[tuple[int, str]] = []

    for subject in subjects:
        code = subject["subject_code"].upper()
        aliases = {
            code.casefold(),
            _normalise_text(subject["subject_name"]),
            _normalise_text(subject["short_name"]),
            *SUBJECT_ALIASES.get(code, set()),
        }
        for alias in aliases:
            alias = _normalise_text(alias)
            if alias and _contains_phrase(normalised, alias):
                candidates.append((len(alias), code))

    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def _extract_unit_numbers(message: str) -> tuple[int, ...]:
    normalised = _normalise_text(message)
    unit_numbers: set[int] = set()

    for match in re.finditer(r"\bunit\s*(\d{1,2})\b", normalised):
        unit_numbers.add(int(match.group(1)))

    for match in re.finditer(
        r"\bunits\s*((?:\d{1,2}\s*(?:(?:and|,|\s)\s*)?)+)",
        normalised,
    ):
        unit_numbers.update(int(value) for value in re.findall(r"\d{1,2}", match.group(1)))

    return tuple(sorted(unit_numbers))


def _detect_preparation_level(normalised: str) -> str | None:
    patterns = (
        ("revision_only", ("revision only", "only revision", "ready for revision")),
        ("mostly_prepared", ("mostly prepared", "almost prepared", "mostly done")),
        ("basics_completed", ("basics completed", "basic completed", "basics done")),
        ("not_started", ("not started", "haven t started", "have not started")),
    )
    for level, phrases in patterns:
        if any(_contains_phrase(normalised, phrase) for phrase in phrases):
            return level
    return None


def _extract_score(message: str) -> tuple[float | None, float | None]:
    normalised = _normalise_text(message)
    explicit_fraction = re.search(
        r"\b(?:i\s+)?(?:scored|got|score(?:\s+is)?)\s+(\d+(?:\.\d+)?)\s+(?:out\s+of|/)\s+(\d+(?:\.\d+)?)\b",
        normalised,
    )
    if explicit_fraction:
        return float(explicit_fraction.group(1)), float(explicit_fraction.group(2))

    compact_fraction = re.search(r"\b(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\b", message)
    if compact_fraction and re.search(r"\b(?:scored|got|score|marks?)\b", normalised):
        return float(compact_fraction.group(1)), float(compact_fraction.group(2))

    score_only = re.search(
        r"\b(?:i\s+)?(?:scored|got|score(?:\s+is)?)\s+(\d+(?:\.\d+)?)\b",
        normalised,
    )
    if score_only:
        return float(score_only.group(1)), None
    return None, None


def _detect_credit_filter(normalised: str) -> int | None:
    numeric = re.search(r"\b(\d+)\s+credits?\b", normalised)
    if numeric:
        return int(numeric.group(1))

    words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
    }
    for word, value in words.items():
        if re.search(rf"\b{word}\s+credits?\b", normalised):
            return value
    return None


def _infer_unit_from_topics(message: str, subject_code: str) -> int | None:
    normalised = _normalise_text(message)
    subject = load_subject(subject_code)

    for unit in subject["units"]:
        title = _normalise_text(unit["title"])
        if len(title) >= 4 and _contains_phrase(normalised, title):
            return unit["number"]

    ignored = {
        "a",
        "an",
        "and",
        "are",
        "about",
        "explain",
        "for",
        "from",
        "help",
        "in",
        "is",
        "me",
        "of",
        "on",
        "subject",
        "teach",
        "the",
        "to",
        "unit",
        "what",
        "with",
    }
    subject_words = set(_normalise_text(subject["subject_name"]).split())
    subject_words.update(_normalise_text(subject["short_name"]).split())
    query_words = {
        word
        for word in normalised.split()
        if len(word) >= 3 and word not in ignored and word not in subject_words
    }

    best_unit = None
    best_score = 0
    for unit in subject["units"]:
        unit_words = set(_normalise_text(unit["title"]).split())
        for topic in unit["topics"]:
            unit_words.update(_normalise_text(topic).split())
        score = len(query_words & unit_words)
        if score > best_score:
            best_score = score
            best_unit = unit["number"]

    return best_unit if best_score >= 2 else None


def _format_credit_list(
    subjects: list[dict[str, Any]],
    credit_filter: int | None,
) -> str:
    selected = [
        subject
        for subject in subjects
        if credit_filter is None or subject["credits"] == credit_filter
    ]
    if not selected:
        return f"I couldn't find a {credit_filter}-credit subject in your catalog."

    heading = (
        f"🎓 {credit_filter}-CREDIT SUBJECTS"
        if credit_filter is not None
        else "🎓 SUBJECT CREDITS"
    )
    lines = [heading, ""]
    lines.extend(
        f"• {subject['short_name']} ({subject['subject_code']}) — "
        f"{subject['credits']} credit(s)"
        for subject in subjects
        if subject in selected
    )
    return "\n".join(lines)


def route_academic_message(
    message: str,
    subjects: list[dict[str, Any]],
) -> AcademicRoute:
    normalised = _normalise_text(message)
    words = set(normalised.split())
    subject_code = detect_subject_code(message, subjects)
    unit_numbers = _extract_unit_numbers(message)
    preparation_level = _detect_preparation_level(normalised)
    latest_score, latest_score_max = _extract_score(message)

    completion_words = bool(
        re.search(r"\b(?:completed|finished|covered|done\s+with)\b", normalised)
    )
    incomplete_words = bool(
        re.search(
            r"\b(?:not\s+completed|haven\s+t\s+completed|have\s+not\s+completed|incomplete|undo)\b",
            normalised,
        )
    )

    if subject_code and (
        preparation_level
        or latest_score is not None
        or (unit_numbers and (completion_words or incomplete_words))
    ):
        action = None
        if unit_numbers and (completion_words or incomplete_words):
            action = "remove" if incomplete_words else "add"
        return AcademicRoute(
            kind="progress_update",
            intent="progress",
            subject_code=subject_code,
            unit_numbers=unit_numbers,
            completed_action=action,
            preparation_level=preparation_level,
            latest_score=latest_score,
            latest_score_max=latest_score_max,
        )

    progress_query = (
        "progress" in words
        or _contains_phrase(normalised, "preparation status")
        or _contains_phrase(normalised, "what have i completed")
    )
    if progress_query:
        return AcademicRoute(
            kind="progress_view",
            intent="progress",
            subject_code=subject_code,
        )

    if "credit" in words or "credits" in words:
        if subject_code:
            return AcademicRoute(
                kind="direct",
                intent="credits",
                subject_code=subject_code,
                response=format_subject_credits(subject_code),
            )
        return AcademicRoute(
            kind="direct",
            intent="credits",
            response=_format_credit_list(subjects, _detect_credit_filter(normalised)),
        )

    resource_query = bool(words & RESOURCE_WORDS)
    syllabus_query = bool(words & SYLLABUS_WORDS)

    if resource_query:
        if not subject_code:
            return AcademicRoute(
                kind="direct",
                intent="resources",
                unit_numbers=unit_numbers,
                response=(
                    "Tell me the subject too—for example: "
                    "'Give me COA Unit 4 resources'."
                ),
            )
        try:
            response = (
                format_unit_resources(subject_code, unit_numbers[0])
                if unit_numbers
                else format_subject_resources(subject_code)
            )
        except ValueError as error:
            response = f"⚠️ {error}"
        return AcademicRoute(
            kind="direct",
            intent="resources",
            subject_code=subject_code,
            unit_numbers=unit_numbers,
            response=response,
        )

    if syllabus_query:
        if not subject_code:
            return AcademicRoute(
                kind="direct",
                intent="syllabus",
                unit_numbers=unit_numbers,
                response=(
                    "Tell me the subject too—for example: "
                    "'Show me the DSTL Unit 2 syllabus'."
                ),
            )
        try:
            response = (
                format_unit_syllabus(subject_code, unit_numbers[0])
                if unit_numbers
                else format_subject_syllabus(subject_code)
            )
        except ValueError as error:
            response = f"⚠️ {error}"
        return AcademicRoute(
            kind="direct",
            intent="syllabus",
            subject_code=subject_code,
            unit_numbers=unit_numbers,
            response=response,
        )

    academic_context_query = bool(words & CONTEXT_WORDS) or bool(
        re.search(r"\b(?:what|how|why)\b", normalised)
    )
    if subject_code and academic_context_query:
        if unit_numbers:
            try:
                get_subject_unit(subject_code, unit_numbers[0])
            except ValueError as error:
                return AcademicRoute(
                    kind="direct",
                    intent="explain",
                    subject_code=subject_code,
                    unit_numbers=unit_numbers,
                    response=f"⚠️ {error}",
                )
        if not unit_numbers:
            inferred = _infer_unit_from_topics(message, subject_code)
            unit_numbers = (inferred,) if inferred else ()
        return AcademicRoute(
            kind="context",
            intent="explain",
            subject_code=subject_code,
            unit_numbers=unit_numbers,
        )

    if subject_code and (
        "subject" in words
        or _contains_phrase(normalised, "i mean")
        or len(words) <= 3
    ):
        subject = load_subject(subject_code)
        return AcademicRoute(
            kind="direct",
            intent="subject_reference",
            subject_code=subject_code,
            response=(
                f"Got it—{subject['short_name']} ({subject['subject_code']}). "
                "Ask me for a unit's resources, syllabus topics, credits or an explanation."
            ),
        )

    return AcademicRoute(kind="none")


def infer_preparation_level(completed_units: set[int], total_units: int) -> str:
    completed_count = len(completed_units)
    if completed_count == 0:
        return "not_started"
    if completed_count >= total_units:
        return "revision_only"
    if completed_count >= max(3, total_units - 1):
        return "mostly_prepared"
    return "basics_completed"


def build_academic_context(
    route: AcademicRoute,
    progress: dict[str, Any] | None = None,
) -> str:
    if not route.subject_code:
        return ""

    subject = load_subject(route.subject_code)
    completed = (progress or {}).get("completed_units", [])
    level = (progress or {}).get("preparation_level", "not_started")
    lines = [
        "RAVEN ACADEMIC CONTEXT (trusted local catalog):",
        f"Subject: {subject['subject_name']} ({subject['subject_code']})",
        f"Credits: {subject['credits']}",
        f"Student preparation: {PREPARATION_LEVEL_LABELS.get(level, level)}",
        "Completed units: " + (", ".join(map(str, completed)) if completed else "None"),
    ]

    units = subject["units"]
    if route.unit_numbers:
        try:
            units = [get_subject_unit(route.subject_code, route.unit_numbers[0])]
        except ValueError as error:
            lines.append(f"Catalog warning: {error}")
            units = []

    for unit in units:
        lines.extend(
            [
                "",
                f"Unit {unit['number']}: {unit['title']}",
                "Topics: " + "; ".join(unit["topics"]),
            ]
        )
        resources = unit.get("resources") or []
        if resources:
            lines.append(
                f"Verified resource: {resources[0]['title']} — {resources[0]['url']}"
            )

    lines.extend(
        [
            "",
            "Use this context when answering the user's academic question.",
            "Never say you lack access to the syllabus or stored resource links above.",
            "Do not invent topics, links, marks frequency, or PYQ importance.",
        ]
    )
    return "\n".join(lines)


def format_progress_summary(
    subjects: list[dict[str, Any]],
    progress_by_subject: dict[str, dict[str, Any]],
    subject_code: str | None = None,
) -> str:
    selected = [
        subject
        for subject in subjects
        if subject_code is None or subject["subject_code"] == subject_code
    ]
    if not selected:
        return "I couldn't find that subject in your current semester catalog."

    lines = ["📊 ACADEMIC PREPARATION"]
    for subject in selected:
        progress = progress_by_subject.get(subject["subject_code"], {})
        level = progress.get("preparation_level", "not_started")
        completed = progress.get("completed_units", [])
        completed_text = ", ".join(map(str, completed)) if completed else "None"
        score = progress.get("latest_score")
        score_max = progress.get("latest_score_max")
        if score is None:
            score_text = "Not recorded"
        elif score_max is None:
            score_text = f"{score:g}"
        else:
            score_text = f"{score:g}/{score_max:g}"

        lines.extend(
            [
                "",
                f"{subject['short_name']} ({subject['subject_code']}) • "
                f"{subject['credits']} credit(s)",
                f"Level: {PREPARATION_LEVEL_LABELS.get(level, level)}",
                f"Completed units: {completed_text}",
                f"Latest score: {score_text}",
            ]
        )

    lines.extend(
        [
            "",
            "Update naturally, for example:",
            "'I completed COA Unit 2' or 'I scored 18/30 in COA'.",
        ]
    )
    return "\n".join(lines)
