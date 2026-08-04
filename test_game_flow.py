import unittest
from unittest.mock import patch

import app as webhook_app


def webhook_payload(text):
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "919876543210",
                        "type": "text",
                        "text": {"body": text},
                    }]
                }
            }]
        }]
    }


class GameFlowTests(unittest.TestCase):
    def setUp(self):
        self.client = webhook_app.app.test_client()

    def test_extracts_token_from_supported_play_commands(self):
        self.assertEqual(webhook_app.extract_play_token("play abc123"), "abc123")
        self.assertEqual(webhook_app.extract_play_token(" PLAY + jwt.token "), "jwt.token")
        self.assertIsNone(webhook_app.extract_play_token("play"))
        self.assertIsNone(webhook_app.extract_play_token("display abc123"))

    def test_mock_game_api_url_encodes_token(self):
        with patch.object(webhook_app, "MOCK_GAME_URL", "https://game.test/start"):
            self.assertEqual(
                webhook_app.get_game_url("abc+123/="),
                "https://game.test/start?token=abc%2B123%2F%3D",
            )

    @patch("app.requests.post")
    @patch("app.get_game_url", return_value="https://game.test/start/abc123")
    @patch("app.save_webhook")
    def test_webhook_sends_game_url_to_user(self, save_webhook, get_game_url, post):
        post.return_value.raise_for_status.return_value = None

        response = self.client.post("/webhook", json=webhook_payload("play + abc123"))

        self.assertEqual(response.status_code, 200)
        get_game_url.assert_called_once_with("abc123")
        sent = post.call_args.kwargs["json"]
        self.assertEqual(sent["to"], "919876543210")
        self.assertEqual(
            sent["text"]["body"],
            "Click on 'https://game.test/start/abc123' to start the game.",
        )


if __name__ == "__main__":
    unittest.main()
