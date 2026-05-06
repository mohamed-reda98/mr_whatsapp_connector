# MR WhatsApp Connector

Send WhatsApp messages from Odoo 18 via a self-hosted Node.js sidecar that
runs [whatsapp-web.js](https://wwebjs.dev/). No official WhatsApp Business API
account is required.

> **Heads up.** Automating WhatsApp Web is against WhatsApp's Terms of Service.
> Numbers do get banned. Use a non-personal number, expect the session to be
> disposable, and treat this as a workshop tool — not a guaranteed channel.

## What it gives you

- A sidecar service (`sidecar/`) you run alongside Odoo. Talks to
  `whatsapp-web.js`, exposes a small HTTP API.
- An Odoo module that:
  - Adds **Send WhatsApp** buttons to Contacts, Sales Orders, Invoices,
    Purchase Orders, and CRM Leads.
  - Provides a compose **wizard** with template picker, attachment support, and
    chatter logging.
  - Has a **Templates** model with inline-template (`{{ object.field }}`)
    rendering powered by `mail.render.mixin`.
  - Has a **Messages** log (outgoing + optional incoming) with delivery
    status updates (`sent → delivered → read`).
  - Has a **Settings → WhatsApp** panel with QR pairing, status indicator,
    and logout button.

## Install

### 1. Install the sidecar

```bash
cd /home/mohamed/odoo/odoo18/mymodules/mr_whatsapp_connector/mr_whatsapp_connector/sidecar
npm install
cp .env.example .env
# edit .env:
#   SIDECAR_API_KEY=<long random string>
#   ODOO_WEBHOOK_URL=http://localhost:8018/mr_whatsapp/webhook
npm start
```

### 2. Install the Odoo module

The addons path is already wired up in `odoo18.conf`. Restart Odoo, then:

1. Apps → *Update Apps List*.
2. Search `MR WhatsApp Connector` → Install.
3. Go to **Settings → WhatsApp**.
4. Enter the **Sidecar URL** (e.g. `http://localhost:3000`) and the same
   **API Key** you put in `.env`.
5. Save. The QR widget polls the sidecar; scan the QR with WhatsApp
   (Linked Devices → Link a Device).
6. Once the badge says *Connected*, send a test from any contact.

## Sending a message

From any contact, sales order, invoice, PO, or lead:

1. Click **Send WhatsApp** (or the WhatsApp smart button on contacts).
2. Pick a template (optional). The body is rendered with the record's data.
3. Adjust the message, attach files if needed.
4. **Send**. The message is logged under **WhatsApp → Messages** and posted
   to the source record's chatter.

## Templates

Templates use Odoo's **inline_template** engine:

```
Hi {{ object.partner_id.name }}, your order {{ object.name }}
for a total of {{ object.amount_total }} {{ object.currency_id.name }}
has been confirmed.
```

You can also attach a static file or auto-render a report (PDF) with each
template.

## Receiving messages

If `Log Incoming Messages` is enabled and `ODOO_WEBHOOK_URL` is set in the
sidecar's `.env`, every received message is logged in **WhatsApp → Messages**
with `direction = Incoming`. (Auto-reply / chatbot flows are out of scope for v1.)

## Architecture

```
+----------------+   HTTPS/JSON   +---------------------+   Puppeteer    +-------------+
|  Odoo (Python) | <------------> |  Node.js Sidecar    | <------------> | WhatsApp Web|
|  this module   |   X-API-Key    |  whatsapp-web.js    |    Chromium    |   (browser) |
+----------------+                +---------------------+                +-------------+
        ^                                  |
        |          POST /mr_whatsapp/webhook (incoming + ACKs)
        +----------------------------------+
```

## Limits / scope of v1

- Single WhatsApp account per Odoo instance.
- No groups / broadcast lists.
- No auto-reply / chatbot logic.
- ACK mapping is best-effort (whatsapp-web.js doesn't expose all states reliably).
- Reconnect on `disconnected` requires re-scanning the QR.
