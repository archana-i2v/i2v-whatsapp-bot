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
        self.database_file = Path(self.temp_dir.name) / "app.db"
        self.file_patch = patch.object(webhook_app, "DATA_FILE", self.data_file)
        self.database_patch = patch.object(webhook_app, "DATABASE_FILE", self.database_file)
        self.employee_numbers_patch = patch.object(webhook_app, "EMPLOYEE_PHONE_NUMBERS", "")
        self.file_patch.start()
        self.database_patch.start()
        self.employee_numbers_patch.start()
        self.client = webhook_app.app.test_client()

    def tearDown(self):
        self.file_patch.stop()
        self.database_patch.stop()
        self.employee_numbers_patch.stop()
        self.temp_dir.cleanup()

    def register_employee(self, phone):
        webhook_app.initialize_database()
        with webhook_app.closing(webhook_app.sqlite3.connect(self.database_file)) as connection:
            with connection:
                connection.execute(
                    "INSERT INTO employees (phone_number) VALUES (?)",
                    (phone,),
                )

    @patch("app.requests.post")
    def test_registered_employee_can_mark_attendance(self, post):
        post.return_value.raise_for_status.return_value = None
        self.register_employee("919876543210")

        self.client.post("/webhook", json=payload(
            {"from": "919876543210", "text": {"body": "  HI  "}},
        ))

        sent = post.call_args.kwargs["json"]
        self.assertEqual(sent["type"], "interactive")
        self.assertEqual(sent["interactive"]["type"], "button")
        self.assertEqual(
            sent["interactive"]["action"]["buttons"][0]["reply"]["id"],
            "attendance_yes",
        )
        self.assertEqual(
            sent["interactive"]["action"]["buttons"][1]["reply"]["id"],
            "attendance_no",
        )

        self.client.post("/webhook", json=payload({
            "from": "919876543210",
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": "attendance_yes", "title": "Yes"},
            },
        }))

        sent = post.call_args.kwargs["json"]
        self.assertIn("marked Present", sent["text"]["body"])
        with webhook_app.closing(webhook_app.sqlite3.connect(self.database_file)) as connection:
            attendance = connection.execute(
                "SELECT status FROM attendance"
            ).fetchall()
        self.assertEqual(attendance, [("Present",)])

        self.client.post("/webhook", json=payload({
            "from": "919876543210",
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": "attendance_yes", "title": "Yes"},
            },
        }))
        self.assertIn("already marked", post.call_args.kwargs["json"]["text"]["body"])

    @patch("app.requests.post")
    def test_attendance_no_sends_default_reply(self, post):
        post.return_value.raise_for_status.return_value = None

        self.client.post("/webhook", json=payload({
            "from": "919876543210",
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": "attendance_no", "title": "No"},
            },
        }))

        self.assertEqual(
            post.call_args.kwargs["json"]["text"]["body"],
            webhook_app.DEFAULT_REPLY,
        )

    @patch("app.requests.post")
    def test_unregistered_employee_is_rejected_after_yes(self, post):
        post.return_value.raise_for_status.return_value = None

        self.client.post("/webhook", json=payload(
            {"from": "911234567890", "text": {"body": "Hi"}},
        ))

        sent = post.call_args.kwargs["json"]
        self.assertEqual(sent["type"], "interactive")
        self.assertEqual(sent["interactive"]["type"], "button")

        self.client.post("/webhook", json=payload({
            "from": "911234567890",
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": "attendance_yes", "title": "Yes"},
            },
        }))

        sent = post.call_args.kwargs["json"]
        self.assertIn("not an i2V employee", sent["text"]["body"])
        self.assertIn("9989309953", sent["text"]["body"])

    def test_mock_employees_are_created(self):
        webhook_app.initialize_database()
        with webhook_app.closing(webhook_app.sqlite3.connect(self.database_file)) as connection:
            employees = connection.execute(
                """SELECT employee_code, phone_number, name, department,
                          designation, status
                   FROM employees ORDER BY phone_number"""
            ).fetchall()
        self.assertIn(
            ("I2V001", "919989309953", "Archana Singh", "IT", "IT Head", "active"),
            employees,
        )
        self.assertIn(
            ("I2V002", "630202065047", "SVS", "Management", "Managing Director", "active"),
            employees,
        )
        self.assertIn(
            (
                "I2V003",
                "916350369740",
                "Employee 6350369740",
                "IT",
                "Software Engineer",
                "active",
            ),
            employees,
        )

    def test_indian_phone_number_is_normalized(self):
        self.assertEqual(webhook_app.normalize_phone("9989309953"), "919989309953")
        self.assertEqual(webhook_app.normalize_phone("+91 99893 09953"), "919989309953")

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

    @patch("app.requests.post")
    def test_messages_page_shows_phone_time_and_escaped_text(self, post):
        post.return_value.raise_for_status.return_value = None
        self.client.post("/webhook", json=payload({
            "from": "919999999999",
            "timestamp": "1783773000",
            "type": "text",
            "text": {"body": "Price < 100?"},
        }))

        response = self.client.get("/messages")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"919999999999", response.data)
        self.assertIn(b"IST", response.data)
        self.assertIn(b"Price &lt; 100?", response.data)
        self.assertNotIn(b"Price < 100?", response.data)


if __name__ == "__main__":
    unittest.main()
