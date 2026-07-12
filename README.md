# WhatsApp Webhook

## Environment Variables
VERIFY_TOKEN=i2vWebhook2026
ACCESS_TOKEN=<Meta permanent access token>
PHONE_NUMBER_ID=<Phone Number ID>
ATTENDANCE_FLOW_ID=<Published Meta WhatsApp Flow ID>
EMPLOYEE_PHONE_NUMBERS=919876543210,919999999999

Create the attendance Flow in WhatsApp Manager, import `attendance_flow.json`,
publish it, and set its ID as `ATTENDANCE_FLOW_ID` in Render.
Set employee WhatsApp numbers in international format, without `+`, as the
comma-separated `EMPLOYEE_PHONE_NUMBERS` value. They are added to the SQLite
`employees` table when the webhook receives a message.

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

View captured sender numbers:
https://YOUR-RENDER-APP.onrender.com/numbers

View numbers that sent "hi":
https://YOUR-RENDER-APP.onrender.com/hi-numbers

View phone numbers, message dates/times, and message contents:
https://YOUR-RENDER-APP.onrender.com/messages

Run tests:
python -m unittest -v

Note: Render's default filesystem is ephemeral. Use a Render persistent disk or a
database if these records must survive deployments and service restarts.
