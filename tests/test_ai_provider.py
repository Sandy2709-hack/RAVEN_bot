import unittest
from unittest.mock import Mock, patch

import ai_provider


class AIProviderTests(unittest.TestCase):
    @patch("ai_provider.requests.post")
    def test_groq_request_uses_key_model_and_messages(self, mock_post) -> None:
        response = Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": "  Hello from Groq  "}}]
        }
        mock_post.return_value = response
        messages = [{"role": "user", "content": "Hello"}]

        with (
            patch.object(ai_provider, "GROQ_API_KEY", "secret-key"),
            patch.object(ai_provider, "GROQ_MODEL", "test-model"),
        ):
            reply = ai_provider.ask_groq(messages)

        self.assertEqual(reply, "Hello from Groq")
        response.raise_for_status.assert_called_once_with()
        request = mock_post.call_args
        self.assertEqual(
            request.kwargs["headers"]["Authorization"],
            "Bearer secret-key",
        )
        self.assertEqual(request.kwargs["json"]["model"], "test-model")
        self.assertEqual(request.kwargs["json"]["messages"], messages)

    @patch("ai_provider.ask_groq", return_value="cloud")
    @patch("ai_provider.ask_ollama", return_value="local")
    def test_dispatches_to_configured_provider(
        self,
        mock_ollama,
        mock_groq,
    ) -> None:
        with patch.object(ai_provider, "AI_PROVIDER", "groq"):
            self.assertEqual(ai_provider.ask_ai([]), "cloud")
        mock_groq.assert_called_once_with([])
        mock_ollama.assert_not_called()

        mock_groq.reset_mock()
        with patch.object(ai_provider, "AI_PROVIDER", "ollama"):
            self.assertEqual(ai_provider.ask_ai([]), "local")
        mock_ollama.assert_called_once_with([])
        mock_groq.assert_not_called()


if __name__ == "__main__":
    unittest.main()
