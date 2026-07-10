from flask import Flask, request
import requests, os, json
app=Flask(__name__)
VERIFY_TOKEN=os.getenv("VERIFY_TOKEN")
ACCESS_TOKEN=os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID=os.getenv("PHONE_NUMBER_ID")

@app.get("/")
def home():
    return "i2V WhatsApp Webhook Running"

@app.get("/webhook")
def verify():
    if request.args.get("hub.mode")=="subscribe" and request.args.get("hub.verify_token")==VERIFY_TOKEN:
        return request.args.get("hub.challenge"),200
    return "Verification Failed",403

@app.post("/webhook")
def webhook():
    body=request.get_json()
    print(json.dumps(body,indent=2))
    try:
        value=body["entry"][0]["changes"][0]["value"]
        if "messages" in value:
            msg=value["messages"][0]
            phone=msg["from"]
            text=msg.get("text",{}).get("body","")
            print(phone,text)
            url=f"https://graph.facebook.com/v23.0/{PHONE_NUMBER_ID}/messages"
            headers={"Authorization":f"Bearer {ACCESS_TOKEN}","Content-Type":"application/json"}
            payload={"messaging_product":"whatsapp","to":phone,"type":"text","text":{"body":"Thank you for contacting i2V Consulting Private Limited.\n\nWe have received your message and will get back to you shortly.\n\nFor more details call 9989309953."}}
            requests.post(url,headers=headers,json=payload)
    except Exception as e:
        print(e)
    return "EVENT_RECEIVED",200

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
