import os

from dotenv import load_dotenv


load_dotenv()


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
AI_PROVIDER = os.getenv("AI_PROVIDER", "ollama").strip().casefold()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "").strip()
OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434/api/chat",
).strip()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile",
).strip()
GROQ_URL = os.getenv(
    "GROQ_URL",
    "https://api.groq.com/openai/v1/chat/completions",
).strip()

RECENT_MESSAGE_LIMIT = 20
LONG_TERM_MEMORY_LIMIT = 20
OLLAMA_TIMEOUT_SECONDS = 120
GROQ_TIMEOUT_SECONDS = 60


def validate_settings() -> None:
    missing = []

    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")

    if AI_PROVIDER not in {"ollama", "groq"}:
        raise ValueError("AI_PROVIDER must be either 'ollama' or 'groq'")

    if AI_PROVIDER == "ollama" and not OLLAMA_MODEL:
        missing.append("OLLAMA_MODEL")

    if AI_PROVIDER == "groq" and not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")

    if AI_PROVIDER == "groq" and not GROQ_MODEL:
        missing.append("GROQ_MODEL")

    if missing:
        names = ", ".join(missing)
        raise ValueError(f"Missing required .env values: {names}")
