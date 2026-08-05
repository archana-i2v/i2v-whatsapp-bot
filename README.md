# WhatsApp Webhook

## Environment Variables
VERIFY_TOKEN=i2vWebhook2026
ACCESS_TOKEN=<Meta permanent access token>
PHONE_NUMBER_ID=<Phone Number ID>
GAME_API_URL=https://tambolav2-gnfshrhpf2a6byhb.southindia-01.azurewebsites.net/api/v2/join/resolve
GAME_API_TIMEOUT=15
ATTENDANCE_FLOW_ID=<Published Meta WhatsApp Flow ID>
EMPLOYEE_PHONE_NUMBERS=919876543210,919999999999
I2V_API_BASE_URL=https://log.I2vWorld.Com/I2vUatApi
I2V_API_USERNAME=Admin
I2V_API_PASSWORD=<API password>
I2V_ATTENDANCE_USERNAME=Admin
I2V_APP_ID=APP001
I2V_API_TIMEOUT=15

Send `play TOKEN` or `play + TOKEN` using any capitalization. The webhook sends
the user-provided token to the Tambola resolver API as the `token` query
parameter and forwards its `replyText` directly to the WhatsApp user. Invalid
and expired tokens receive a clear error message. The resolver result also
contains `whatsappPhoneNumber`, populated from the incoming WhatsApp message.

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

After deployment, replace `<service-name>` with the service name shown in the
Render dashboard. For example: `https://<service-name>.onrender.com/webhook`.

Available routes:

- Webhook callback and verification: `/webhook`
- Deployment health and Git revision: `/health`
- Captured sender numbers: `/numbers`
- Numbers that sent "hi": `/hi-numbers`
- Phone numbers, message times, and message contents: `/messages`

Run tests:
python -m unittest -v

Note: Render's default filesystem is ephemeral. Use a Render persistent disk or a
database if these records must survive deployments and service restarts.
