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

    @patch("app.requests.post")
    def test_resolver_api_receives_token(self, post):
        post.return_value.json.return_value = {
            "valid": True,
            "joinUrl": "https://game.test/join/TBLS6L39C",
            "replyText": "Welcome to Tambola!",
        }
        post.return_value.raise_for_status.return_value = None

        result = webhook_app.resolve_game_token("TBLS6L39C")

        self.assertTrue(result["valid"])
        post.assert_called_once_with(
            webhook_app.GAME_API_URL,
            headers={"Content-Type": "application/json"},
            json={"token": "TBLS6L39C"},
            timeout=webhook_app.GAME_API_TIMEOUT,
        )

    @patch("app.resolve_game_token")
    def test_api_reply_text_is_forwarded_unchanged(self, resolve):
        reply_text = "🎉 Welcome to Bayer Tambola!\nhttps://game.test/join/TBLS6L39C"
        resolve.return_value = {
            "valid": True,
            "joinUrl": "https://game.test/join/TBLS6L39C",
            "replyText": reply_text,
        }

        self.assertEqual(webhook_app.game_reply_for_message("PlAy TBLS6L39C"), reply_text)
        resolve.assert_called_once_with("TBLS6L39C")

    @patch("app.resolve_game_token", return_value={"valid": False, "reason": "EXPIRED_TOKEN"})
    def test_expired_token_has_clear_reply(self, resolve):
        reply = webhook_app.game_reply_for_message("PLAY TBLEXPIRED")
        self.assertIn("expired", reply)

    @patch("app.requests.post")
    @patch("app.resolve_game_token")
    @patch("app.save_webhook")
    def test_webhook_sends_api_reply_text_to_user(self, save_webhook, resolve, post):
        post.return_value.raise_for_status.return_value = None
        resolve.return_value = {
            "valid": True,
            "joinUrl": "https://game.test/join/TBLS6L39C",
            "replyText": "🎉 Welcome!\nhttps://game.test/join/TBLS6L39C",
        }

        response = self.client.post("/webhook", json=webhook_payload("PLAY + TBLS6L39C"))

        self.assertEqual(response.status_code, 200)
        resolve.assert_called_once_with("TBLS6L39C")
        sent = post.call_args.kwargs["json"]
        self.assertEqual(sent["to"], "919876543210")
        self.assertEqual(
            sent["text"]["body"],
            "🎉 Welcome!\nhttps://game.test/join/TBLS6L39C",
        )


if __name__ == "__main__":
    unittest.main()
