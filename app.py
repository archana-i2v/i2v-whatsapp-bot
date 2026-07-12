from flask import Flask, request
import requests, os, json, sqlite3
from pathlib import Path
from datetime import datetime, timezone
from html import escape
from zoneinfo import ZoneInfo
from contextlib import closing

app = Flask(__name__)
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "I2vWebhook2026")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "")
ATTENDANCE_FLOW_ID = os.getenv("ATTENDANCE_FLOW_ID", "")
EMPLOYEE_PHONE_NUMBERS = os.getenv("EMPLOYEE_PHONE_NUMBERS", "")
MOCK_EMPLOYEES = (
    ("MOCK001", "910000000001", "Mock Employee One", "Testing", "Tester", "active"),
    ("MOCK002", "910000000002", "Mock Employee Two", "Testing", "Tester", "active"),
    ("I2V001", "919989309953", "Archana Singh", "IT", "IT Head", "active"),
    ("I2V002", "630202065047", "SVS", "Management", "Managing Director", "active"),
    ("I2V003", "916350369740", "Employee 6350369740", "IT", "Software Engineer", "active"),
)
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DATA_FILE = DATA_DIR / "messages.log"
DATABASE_FILE = DATA_DIR / "app.db"
INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")

DEFAULT_REPLY = (
    "Thank you for contacting i2V Consulting Private Limited.\n\n"
    "We have received your message and will get back to you shortly.\n\n"
    "For more details call 9989309953."
)


def india_now():
    return datetime.now(INDIA_TIMEZONE)


def reply_for_message(text):
    """Choose an automatic reply for an incoming text message."""
    replies = {
        "hi": "Do you want to mark attendance?",
        "play": "OK, I will send you details of the game.",
    }
    return replies.get(text.strip().lower(), DEFAULT_REPLY)


def attendance_flow_payload(phone):
    """Build the interactive message that opens the published attendance Flow."""
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "flow",
            "header": {"type": "text", "text": "Daily attendance"},
            "body": {"text": "Mark attendance and enter your day details."},
            "footer": {"text": "i2V Consulting Private Limited"},
            "action": {
                "name": "flow",
                "parameters": {
                    "flow_message_version": "3",
                    "flow_token": f"attendance-{phone}",
                    "flow_id": ATTENDANCE_FLOW_ID,
                    "flow_cta": "Mark attendance",
                    "flow_action": "navigate",
                    "flow_action_payload": {"screen": "ATTENDANCE"},
                },
            },
        },
    }


def attendance_button_payload(phone, now=None):
    """Ask a registered employee whether they want to add attendance."""
    now = now or india_now()
    formatted_time = now.strftime("%d %b %Y at %I:%M %p IST")
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": f"Do you want to add attendance for today, {formatted_time}?"
            },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {"id": "attendance_yes", "title": "Yes"},
                    },
                    {
                        "type": "reply",
                        "reply": {"id": "attendance_no", "title": "No"},
                    },
                ]
            },
        },
    }


def greeting_payload(phone, now=None):
    """Return a holiday message on Sunday or the attendance question otherwise."""
    now = now or india_now()
    if now.weekday() == 6:
        return {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {
                "body": (
                    f"Today, {now.strftime('%d %b %Y')}, is Sunday. "
                    "It is a holiday and we are not working today."
                )
            },
        }
    return attendance_button_payload(phone, now)


def initialize_database():
    """Create the employee table and add numbers supplied by the environment."""
    with closing(sqlite3.connect(DATABASE_FILE)) as connection:
        with connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_code TEXT UNIQUE,
                    phone_number TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL DEFAULT '',
                    department TEXT NOT NULL DEFAULT '',
                    designation TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id INTEGER NOT NULL,
                    attendance_date TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Present',
                    marked_at TEXT NOT NULL,
                    UNIQUE(employee_id, attendance_date),
                    FOREIGN KEY (employee_id) REFERENCES employees(id)
                )
            """)
            numbers = [number.strip().lstrip("+") for number in EMPLOYEE_PHONE_NUMBERS.split(",")]
            # Add new columns when upgrading a database created by an older app version.
            existing_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(employees)")
            }
            migrations = {
                "employee_code": "ALTER TABLE employees ADD COLUMN employee_code TEXT",
                "department": "ALTER TABLE employees ADD COLUMN department TEXT NOT NULL DEFAULT ''",
                "designation": "ALTER TABLE employees ADD COLUMN designation TEXT NOT NULL DEFAULT ''",
                "status": "ALTER TABLE employees ADD COLUMN status TEXT NOT NULL DEFAULT 'active'",
                "created_at": "ALTER TABLE employees ADD COLUMN created_at TEXT",
            }
            for column, statement in migrations.items():
                if column not in existing_columns:
                    connection.execute(statement)
            connection.executemany("""
                INSERT INTO employees
                    (employee_code, phone_number, name, department, designation, status)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(phone_number) DO UPDATE SET
                    employee_code = excluded.employee_code,
                    name = excluded.name,
                    department = excluded.department,
                    designation = excluded.designation,
                    status = excluded.status
            """, MOCK_EMPLOYEES)
            connection.executemany(
                "INSERT OR IGNORE INTO employees (phone_number, status) VALUES (?, 'active')",
                [(normalize_phone(number),) for number in numbers if number],
            )


def is_registered_employee(phone):
    initialize_database()
    normalized_phone = normalize_phone(phone)
    with closing(sqlite3.connect(DATABASE_FILE)) as connection:
        employee = connection.execute(
            "SELECT 1 FROM employees WHERE phone_number = ? AND status = 'active'",
            (normalized_phone,),
        ).fetchone()
    return employee is not None


def mark_employee_present(phone):
    """Mark a registered employee present once for the current India date."""
    initialize_database()
    normalized_phone = normalize_phone(phone)
    now = datetime.now(INDIA_TIMEZONE)
    with closing(sqlite3.connect(DATABASE_FILE)) as connection:
        with connection:
            employee = connection.execute(
                "SELECT id FROM employees WHERE phone_number = ? AND status = 'active'",
                (normalized_phone,),
            ).fetchone()
            if employee is None:
                return "not_registered"
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO attendance
                    (employee_id, attendance_date, status, marked_at)
                VALUES (?, ?, 'Present', ?)
                """,
                (employee[0], now.date().isoformat(), now.isoformat()),
            )
    return "marked" if cursor.rowcount else "already_marked"


def normalize_phone(phone):
    """Normalize Indian mobile numbers to the format WhatsApp webhooks use."""
    digits = "".join(character for character in str(phone) if character.isdigit())
    if len(digits) == 10:
        return "91" + digits
    return digits


def incoming_action(message):
    """Return normalized text or a reply-button ID from an inbound message."""
    if message.get("type", "text") == "text":
        return message.get("text", {}).get("body", "").strip().lower()
    if message.get("type") == "interactive":
        interactive = message.get("interactive", {})
        reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
        return reply.get("id", "").strip().lower()
    if message.get("type") == "button":
        return message.get("button", {}).get("payload", "").strip().lower()
    return ""

def save_webhook(body):
    record = {
        "received_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "body": body,
    }
    with DATA_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False))
        f.write("\n")


def iter_messages(body):
    """Yield every inbound message from a WhatsApp webhook payload."""
    if not isinstance(body, dict):
        return

    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                if isinstance(message, dict):
                    yield message


def load_saved_numbers():
    if not DATA_FILE.exists():
        return []

    numbers = []
    with DATA_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                for msg in iter_messages(record.get("body", {})):
                    phone = msg.get("from")
                    if phone:
                        numbers.append(phone)
            except Exception:
                continue
    return sorted(set(numbers))


def load_hi_numbers():
    if not DATA_FILE.exists():
        return []

    hi_numbers = []
    with DATA_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                for msg in iter_messages(record.get("body", {})):
                    phone = msg.get("from")
                    text = msg.get("text", {}).get("body", "").strip().lower()
                    if phone and text == "hi":
                        hi_numbers.append(phone)
            except Exception:
                continue
    return sorted(set(hi_numbers))


def message_text(message):
    """Return readable content for text and common non-text WhatsApp messages."""
    message_type = message.get("type", "text")
    if message_type == "text":
        return message.get("text", {}).get("body", "")
    if message_type == "button":
        return message.get("button", {}).get("text", "[button response]")
    if message_type == "interactive":
        interactive = message.get("interactive", {})
        flow_reply = interactive.get("nfm_reply", {})
        if flow_reply.get("response_json"):
            try:
                response = json.loads(flow_reply["response_json"])
                return "Attendance form: " + json.dumps(response, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                return flow_reply["response_json"]
        response = interactive.get("button_reply") or interactive.get("list_reply") or {}
        return response.get("title") or response.get("id") or "[interactive response]"

    media = message.get(message_type, {})
    caption = media.get("caption", "") if isinstance(media, dict) else ""
    return caption or f"[{message_type}]"


def message_datetime(message, received_at):
    """Use WhatsApp's sent timestamp, falling back to webhook receipt time."""
    try:
        value = datetime.fromtimestamp(int(message["timestamp"]), timezone.utc)
    except (KeyError, TypeError, ValueError, OSError):
        try:
            value = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
        except (AttributeError, TypeError, ValueError):
            return "Unknown"
    return value.astimezone(INDIA_TIMEZONE).strftime("%d %b %Y, %I:%M:%S %p IST")


def load_message_rows():
    if not DATA_FILE.exists():
        return []

    rows = []
    with DATA_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
                for msg in iter_messages(record.get("body", {})):
                    phone = msg.get("from")
                    if phone:
                        rows.append({
                            "phone": phone,
                            "time": message_datetime(msg, record.get("received_at")),
                            "message": message_text(msg),
                        })
            except (json.JSONDecodeError, TypeError):
                continue
    return list(reversed(rows))


@app.get("/")
def home():
    return "i2V WhatsApp Webhook Running"

@app.get("/webhook")
def verify():
    if request.args.get("hub.mode")=="subscribe" and request.args.get("hub.verify_token")==VERIFY_TOKEN:
        return request.args.get("hub.challenge"),200
    return "Verification Failed",403

@app.get("/numbers")
def list_numbers():
    numbers = load_saved_numbers()
    return {"numbers": numbers}


@app.get("/hi-numbers")
def list_hi_numbers():
    numbers = load_hi_numbers()
    html = "<h1>Phone numbers who sent 'hi'</h1>"
    html += "<ul>"
    for number in numbers:
        html += f"<li>{escape(number)}</li>"
    html += "</ul>"
    return html


@app.get("/messages")
def list_messages():
    rows = load_message_rows()
    table_rows = "".join(
        "<tr>"
        f"<td>{escape(row['phone'])}</td>"
        f"<td>{escape(row['time'])}</td>"
        f"<td>{escape(row['message'])}</td>"
        "</tr>"
        for row in rows
    )
    empty = '<tr><td colspan="3">No messages have been recorded yet.</td></tr>'
    return f"""<!doctype html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>WhatsApp messages</title>
<style>
body{{font-family:Arial,sans-serif;margin:24px;color:#1f2937}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #d1d5db;padding:10px;text-align:left}}
th{{background:#075e54;color:white}}tr:nth-child(even){{background:#f3f4f6}}
</style></head><body><h1>WhatsApp messages</h1>
<p>{len(rows)} message(s), newest first. Times are shown in India Standard Time.</p>
<table><thead><tr><th>Phone number</th><th>Date and time</th><th>Message</th></tr></thead>
<tbody>{table_rows or empty}</tbody></table></body></html>"""


@app.post("/webhook")
def webhook():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return "Invalid JSON", 400

    print(json.dumps(body,indent=2))
    save_webhook(body)
    for msg in iter_messages(body):
        try:
            phone=msg["from"]
            text=msg.get("text",{}).get("body","")
            action = incoming_action(msg)
            print(phone,text)
            url=f"https://graph.facebook.com/v23.0/{PHONE_NUMBER_ID}/messages"
            headers={"Authorization":f"Bearer {ACCESS_TOKEN}","Content-Type":"application/json"}
            if action == "hi":
                payload = greeting_payload(phone)
            elif action == "attendance_yes":
                attendance_result = mark_employee_present(phone)
                if attendance_result == "marked":
                    reply = "Your attendance has been marked Present for today."
                elif attendance_result == "already_marked":
                    reply = "Your attendance is already marked Present for today."
                else:
                    reply = (
                        "You are not an i2V employee. "
                        "Please contact HR at 9989309953."
                    )
                payload = {
                    "messaging_product": "whatsapp",
                    "to": phone,
                    "type": "text",
                    "text": {"body": reply},
                }
            elif action == "attendance_no":
                payload = {
                    "messaging_product": "whatsapp",
                    "to": phone,
                    "type": "text",
                    "text": {"body": DEFAULT_REPLY},
                }
            else:
                payload={
                    "messaging_product": "whatsapp",
                    "to": phone,
                    "type": "text",
                    "text": {"body": reply_for_message(text)},
                }
            response = requests.post(url,headers=headers,json=payload,timeout=15)
            response.raise_for_status()
        except Exception as e:
            print(f"Failed to process message: {e}")
    return "EVENT_RECEIVED",200

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
