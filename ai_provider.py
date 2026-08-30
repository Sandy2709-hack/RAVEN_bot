import logging
import time

import requests

from config import (
    AI_PROVIDER,
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_TIMEOUT_SECONDS,
    GROQ_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
    OLLAMA_URL,
)


logger = logging.getLogger("raven.ai")


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


def ask_groq(messages: list[dict[str, str]]) -> str:
    started_at = time.perf_counter()
    response = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": 0.4,
            "max_completion_tokens": 400,
        },
        timeout=GROQ_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    reply = data["choices"][0]["message"]["content"]

    logger.info(
        "Groq model=%s total=%.2fs",
        GROQ_MODEL,
        time.perf_counter() - started_at,
    )
    return reply.strip()


def ask_ai(messages: list[dict[str, str]]) -> str:
    if AI_PROVIDER == "groq":
        return ask_groq(messages)
    return ask_ollama(messages)


def provider_description() -> str:
    if AI_PROVIDER == "groq":
        return f"Groq ({GROQ_MODEL})"
    return f"Ollama ({OLLAMA_MODEL})"
