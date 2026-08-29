import os

from dotenv import load_dotenv


load_dotenv()


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "").strip()
OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434/api/chat",
).strip()

RECENT_MESSAGE_LIMIT = 20
LONG_TERM_MEMORY_LIMIT = 20
OLLAMA_TIMEOUT_SECONDS = 120


def validate_settings() -> None:
    missing = []

    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")

    if not OLLAMA_MODEL:
        missing.append("OLLAMA_MODEL")

    if missing:
        names = ", ".join(missing)
        raise ValueError(f"Missing required .env values: {names}")
