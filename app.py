from flask import Flask, request
import requests, os, json
from pathlib import Path
from datetime import datetime, timezone
from html import escape

app = Flask(__name__)
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "I2vWebhook2026")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "")
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DATA_FILE = DATA_DIR / "messages.log"

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
            payload={"messaging_product":"whatsapp","to":phone,"type":"text","text":{"body":"Thank you for contacting i2V Consulting Private Limited.\n\nWe have received your message and will get back to you shortly.\n\nFor more details call 9989309953."}}
            response = requests.post(url,headers=headers,json=payload,timeout=15)
            response.raise_for_status()
        except Exception as e:
            print(f"Failed to process message: {e}")
    return "EVENT_RECEIVED",200

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
