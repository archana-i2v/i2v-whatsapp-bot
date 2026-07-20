# WhatsApp Webhook

## Environment Variables
VERIFY_TOKEN=i2vWebhook2026
ACCESS_TOKEN=<Meta permanent access token>
PHONE_NUMBER_ID=<Phone Number ID>
ATTENDANCE_FLOW_ID=<Published Meta WhatsApp Flow ID>
EMPLOYEE_PHONE_NUMBERS=919876543210,919999999999
I2V_API_BASE_URL=https://log.I2vWorld.Com/I2vUatApi
I2V_API_USERNAME=Admin
I2V_API_PASSWORD=<API password>
I2V_ATTENDANCE_USERNAME=Admin
I2V_APP_ID=APP001
I2V_API_TIMEOUT=15

When an employee replies **Yes** to the attendance question, the webhook:

1. Generates an i2V API JWT.
2. Validates the sender's 10-digit mobile number.
3. Raises attendance when the employee is active.
4. Offers **Add activity**, **Add expense**, and **End day** buttons.

The supplied validation API only returns an account status, not the employee's
username. Set `I2V_ATTENDANCE_USERNAME` to the value expected by the attendance
API. If attendance must be raised against a different username for every phone
number, the upstream API must provide that phone-to-username mapping.

Create the attendance Flow in WhatsApp Manager, import `attendance_flow.json`,
publish it, and set its ID as `ATTENDANCE_FLOW_ID` in Render.
Set employee WhatsApp numbers in international format, without `+`, as the
comma-separated `EMPLOYEE_PHONE_NUMBERS` value. They are added to the SQLite
`employees` table when the webhook receives a message.

For local testing, the employee table also contains these mock records:
- `910000000001` - Mock Employee One
- `910000000002` - Mock Employee Two
- `919989309953` - Archana Singh, IT Head, IT, active
- `630202065047` - SVS, Managing Director, Management, active
- `916350369740` - Employee 6350369740, Software Engineer, IT, active

Employee numbers are normalized to international WhatsApp format. For example,
`9989309953` is stored and matched as `919989309953`.

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
