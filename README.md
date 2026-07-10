# WhatsApp Webhook

## Environment Variables
VERIFY_TOKEN=i2vWebhook2026
ACCESS_TOKEN=<Meta permanent access token>
PHONE_NUMBER_ID=<Phone Number ID>

Run locally:
pip install -r requirements.txt
python app.py

Deploy to Render:
- Push to GitHub
- Create Web Service
- Build: pip install -r requirements.txt
- Start: gunicorn app:app

Webhook URL:
https://YOUR-RENDER-APP.onrender.com/webhook
