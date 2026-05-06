# mr_whatsapp_connector — Node.js sidecar

This sidecar wraps [`whatsapp-web.js`](https://wwebjs.dev/) and exposes an HTTP API
that the Odoo module talks to.

## Requirements
- Node.js 18+
- A working Chromium/Chrome (whatsapp-web.js downloads its own by default; on
  servers without GUI deps you may need `apt install -y libgbm1 libnss3 libxss1
  libasound2 libatk-bridge2.0-0 libgtk-3-0`).

## Install

```bash
cd mr_whatsapp_connector/sidecar
npm install
cp .env.example .env
# edit .env: set SIDECAR_API_KEY and ODOO_WEBHOOK_URL
npm start
```

The first time you start it, the sidecar prints/serves a QR code. Scan it from
WhatsApp on your phone (Settings → Linked Devices → Link a Device). The session
is then stored under `./.wwebjs_auth/` and reused on restart.

## Environment

| Variable           | Required | Description                                                                 |
|--------------------|----------|-----------------------------------------------------------------------------|
| `SIDECAR_API_KEY`  | yes      | Shared secret. Must match Odoo Settings → WhatsApp → Sidecar API Key.       |
| `PORT`             | no       | Listen port (default 3000).                                                 |
| `HOST`             | no       | Listen address (default 127.0.0.1; bind 0.0.0.0 to expose).                 |
| `ODOO_WEBHOOK_URL` | no       | Where to POST inbound events. Usually `http://localhost:8018/mr_whatsapp/webhook`. |
| `CHROME_PATH`      | no       | Path to a system Chromium if you don't want the bundled one.                |

## Endpoints

All endpoints (except `/health`) require `X-API-Key: <SIDECAR_API_KEY>`.

| Method | Path        | Body                                            | Returns                              |
|--------|-------------|-------------------------------------------------|--------------------------------------|
| GET    | `/health`   |                                                 | `{ok:true}`                          |
| GET    | `/status`   |                                                 | `{state, phone, error}`              |
| GET    | `/qr`       |                                                 | `{qr: "data:image/png;base64,..."}`  |
| POST   | `/send`     | `{to, message, attachment?:{filename,mimetype,base64}}` | `{ok, message_id, to}`       |
| POST   | `/logout`   |                                                 | `{ok}`                               |

## Running as a service

A minimal systemd unit:

```ini
[Unit]
Description=mr_whatsapp_connector sidecar
After=network.target

[Service]
WorkingDirectory=/opt/mr_whatsapp_connector/sidecar
EnvironmentFile=/opt/mr_whatsapp_connector/sidecar/.env
ExecStart=/usr/bin/node server.js
Restart=on-failure
User=odoo

[Install]
WantedBy=multi-user.target
```

## Disclaimer

Automating WhatsApp Web is against WhatsApp's Terms of Service. Numbers can be
banned without warning. Use a non-personal number, and assume any automation
session is disposable.
