import unittest
from unittest.mock import patch

import app as webhook_app

TEST_TOKEN = "USER_PROVIDED_TOKEN"
TEST_PHONE = "919876543210"


def webhook_payload(text):
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": TEST_PHONE,
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

    @patch("app.requests.get")
    def test_resolver_api_receives_user_token_as_query_parameter(self, get):
        get.return_value.json.return_value = {
            "valid": True,
            "joinUrl": f"https://game.test/join/{TEST_TOKEN}",
            "replyText": "Welcome to Tambola!",
        }
        get.return_value.raise_for_status.return_value = None

        result = webhook_app.resolve_game_token(TEST_TOKEN, TEST_PHONE)

        self.assertTrue(result["valid"])
        self.assertEqual(result["whatsappPhoneNumber"], TEST_PHONE)
        get.assert_called_once_with(
            webhook_app.GAME_API_URL,
            params={"token": TEST_TOKEN},
            timeout=webhook_app.GAME_API_TIMEOUT,
        )

    @patch("app.resolve_game_token")
    def test_api_reply_text_is_forwarded_unchanged(self, resolve):
        reply_text = f"🎉 Welcome to Bayer Tambola!\nhttps://game.test/join/{TEST_TOKEN}"
        resolve.return_value = {
            "valid": True,
            "joinUrl": f"https://game.test/join/{TEST_TOKEN}",
            "replyText": reply_text,
        }

        self.assertEqual(
            webhook_app.game_reply_for_message(f"PlAy {TEST_TOKEN}", TEST_PHONE),
            reply_text,
        )
        resolve.assert_called_once_with(TEST_TOKEN, TEST_PHONE)

    @patch("app.resolve_game_token", return_value={"valid": False, "reason": "EXPIRED_TOKEN"})
    def test_expired_token_has_clear_reply(self, resolve):
        reply = webhook_app.game_reply_for_message("PLAY TBLEXPIRED", TEST_PHONE)
        self.assertIn("expired", reply)

    @patch("app.requests.post")
    @patch("app.resolve_game_token")
    @patch("app.save_webhook")
    def test_webhook_sends_api_reply_text_to_user(self, save_webhook, resolve, post):
        post.return_value.raise_for_status.return_value = None
        resolve.return_value = {
            "valid": True,
            "joinUrl": f"https://game.test/join/{TEST_TOKEN}",
            "replyText": f"🎉 Welcome!\nhttps://game.test/join/{TEST_TOKEN}",
        }

        response = self.client.post("/webhook", json=webhook_payload(f"PLAY + {TEST_TOKEN}"))

        self.assertEqual(response.status_code, 200)
        resolve.assert_called_once_with(TEST_TOKEN, TEST_PHONE)
        sent = post.call_args.kwargs["json"]
        self.assertEqual(sent["to"], TEST_PHONE)
        self.assertEqual(
            sent["text"]["body"],
            f"🎉 Welcome!\nhttps://game.test/join/{TEST_TOKEN}",
        )

    @patch.dict("app.os.environ", {"RENDER_GIT_COMMIT": "abc123"})
    def test_health_returns_render_commit(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok", "commit": "abc123"})


if __name__ == "__main__":
    unittest.main()
