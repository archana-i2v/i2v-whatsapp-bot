import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as webhook_app


def payload(*messages):
    return {
        "entry": [{"changes": [{"value": {"messages": list(messages)}}]}]
    }


class WebhookTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_file = Path(self.temp_dir.name) / "messages.log"
        self.file_patch = patch.object(webhook_app, "DATA_FILE", self.data_file)
        self.file_patch.start()
        self.client = webhook_app.app.test_client()

    def tearDown(self):
        self.file_patch.stop()
        self.temp_dir.cleanup()

    @patch("app.requests.post")
    def test_incoming_number_is_saved_and_listed(self, post):
        post.return_value.raise_for_status.return_value = None
        body = payload({"from": "919876543210", "text": {"body": "Hello"}})

        response = self.client.post("/webhook", json=body)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/numbers").json, {"numbers": ["919876543210"]})
        post.assert_called_once()
        self.assertEqual(post.call_args.kwargs["json"]["to"], "919876543210")

    @patch("app.requests.post")
    def test_hi_numbers_are_case_insensitive_and_unique(self, post):
        post.return_value.raise_for_status.return_value = None
        self.client.post("/webhook", json=payload(
            {"from": "911111111111", "text": {"body": " Hi "}},
            {"from": "922222222222", "text": {"body": "other"}},
        ))
        self.client.post("/webhook", json=payload(
            {"from": "911111111111", "text": {"body": "HI"}},
        ))

        response = self.client.get("/hi-numbers")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"911111111111", response.data)
        self.assertNotIn(b"922222222222", response.data)

    def test_status_event_and_invalid_json_are_safe(self):
        status = {"entry": [{"changes": [{"value": {"statuses": [{}]}}]}]}
        self.assertEqual(self.client.post("/webhook", json=status).status_code, 200)
        self.assertEqual(
            self.client.post("/webhook", data="not-json", content_type="text/plain").status_code,
            400,
        )


if __name__ == "__main__":
    unittest.main()
