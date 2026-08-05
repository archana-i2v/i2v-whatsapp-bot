from flask import Flask, request
import requests, os, json
from pathlib import Path
from datetime import datetime, timezone
from html import escape
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

app = Flask(__name__)
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "I2vWebhook2026")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "")
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DATA_FILE = DATA_DIR / "messages.log"
INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")
GAME_API_URL = os.getenv(
    "GAME_API_URL",
    "https://tambolav2-gnfshrhpf2a6byhb.southindia-01.azurewebsites.net/api/v2/join/resolve",
)
GAME_API_TIMEOUT = int(os.getenv("GAME_API_TIMEOUT", "15"))

DEFAULT_REPLY = (
    "Thank you for contacting i2V Consulting Private Limited.\n\n"
    "We have received your message and will get back to you shortly.\n\n"
    "For more details call 9989309953."
)


def reply_for_message(text):
    """Choose an automatic reply for an incoming text message."""
    replies = {
        "hi": "Do you want to mark attendance?",
        "Hi": "Do you want to mark attendance?",
        "play": "OK, I will send you details of the game.",
        "Play": "OK, I will send you details of the game.",
    }
    return replies.get(text.strip().lower(), DEFAULT_REPLY)


def extract_play_token(text):
    """Extract TOKEN from either `play TOKEN` or `play + TOKEN`."""
    parts = text.strip().split(maxsplit=1)
    if len(parts) != 2 or parts[0].casefold() != "play":
        return None

    token = parts[1].strip()
    if token.startswith("+"):
        token = token[1:].strip()
    return token or None


def resolve_game_token(token, whatsapp_phone_number):
    """Resolve a token and associate the result with its WhatsApp sender."""
    response = requests.get(
        GAME_API_URL,
        params={"token": token},
        timeout=GAME_API_TIMEOUT,
    )
    response.raise_for_status()
    result = response.json()
    if not isinstance(result, dict):
        raise ValueError("The game API returned an invalid response")
    result["whatsappPhoneNumber"] = whatsapp_phone_number
    return result


def game_reply_for_message(text, whatsapp_phone_number):
    """Return a game-link reply for a play command, or None for other text."""
    token = extract_play_token(text)
    if token is None:
        return None

    result = resolve_game_token(token, whatsapp_phone_number)
    if result.get("valid") is not True:
        reason = str(result.get("reason", "")).upper()
        if reason == "EXPIRED_TOKEN":
            return "This game token has expired. Please request a new token."
        if reason == "INVALID_TOKEN":
            return "This game token is invalid. Please check it and try again."
        return "This game token could not be validated. Please try again."

    reply_text = result.get("replyText")
    if isinstance(reply_text, str) and reply_text.strip():
        return reply_text

    game_url = result.get("joinUrl", "")
    parsed_url = urlsplit(game_url)
    if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
        raise ValueError("The game API response did not contain replyText or a valid joinUrl")
    return f"Click on '{game_url}' to start the game."

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


@app.get("/health")
def health():
    """Expose deployment health and the Render Git revision."""
    return {
        "status": "ok",
        "commit": os.getenv("RENDER_GIT_COMMIT", "local"),
    }

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
            print(phone,text)
            url=f"https://graph.facebook.com/v23.0/{PHONE_NUMBER_ID}/messages"
            headers={"Authorization":f"Bearer {ACCESS_TOKEN}","Content-Type":"application/json"}
            try:
                reply = game_reply_for_message(text, phone) or reply_for_message(text)
            except (requests.RequestException, ValueError) as error:
                print(f"Game API failed: {error}")
                reply = "We could not retrieve the game link right now. Please try again shortly."
            payload={
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "text",
                "text": {"body": reply},
            }
            response = requests.post(url,headers=headers,json=payload,timeout=15)
            response.raise_for_status()
        except Exception as e:
            print(f"Failed to process message: {e}")
    return "EVENT_RECEIVED",200

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
