import unittest
from unittest.mock import patch

import config


class ConfigurationTests(unittest.TestCase):
    def test_groq_requires_its_api_key_but_not_ollama_model(self) -> None:
        with (
            patch.object(config, "TELEGRAM_BOT_TOKEN", "telegram-token"),
            patch.object(config, "AI_PROVIDER", "groq"),
            patch.object(config, "GROQ_API_KEY", "groq-key"),
            patch.object(config, "GROQ_MODEL", "test-model"),
            patch.object(config, "OLLAMA_MODEL", ""),
        ):
            config.validate_settings()

    def test_ollama_requires_model_but_not_groq_key(self) -> None:
        with (
            patch.object(config, "TELEGRAM_BOT_TOKEN", "telegram-token"),
            patch.object(config, "AI_PROVIDER", "ollama"),
            patch.object(config, "OLLAMA_MODEL", "qwen3:1.7b"),
            patch.object(config, "GROQ_API_KEY", ""),
        ):
            config.validate_settings()

    def test_unknown_provider_is_rejected(self) -> None:
        with (
            patch.object(config, "TELEGRAM_BOT_TOKEN", "telegram-token"),
            patch.object(config, "AI_PROVIDER", "unknown"),
        ):
            with self.assertRaisesRegex(ValueError, "AI_PROVIDER"):
                config.validate_settings()


if __name__ == "__main__":
    unittest.main()
