/**
 * mr_whatsapp_connector sidecar
 *
 * Bridges Odoo to whatsapp-web.js.  Exposes:
 *   GET  /health        - liveness
 *   GET  /status        - { state, phone }
 *   GET  /qr            - { qr: "data:image/png;base64,..." | null }
 *   POST /send          - { to, message, attachment? } -> { ok, message_id }
 *   POST /logout        - drops session
 *
 * Outbound: posts events to ODOO_WEBHOOK_URL with X-API-Key header.
 *
 * All endpoints require a matching X-API-Key header.
 */

require('dotenv').config();

const express = require('express');
const axios = require('axios');
const qrcode = require('qrcode');
const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');

const API_KEY = process.env.SIDECAR_API_KEY || '';
const PORT = parseInt(process.env.PORT || '3000', 10);
const HOST = process.env.HOST || '127.0.0.1';
const WEBHOOK_URL = (process.env.ODOO_WEBHOOK_URL || '').trim();
const CHROME_PATH = (process.env.CHROME_PATH || '').trim();

if (!API_KEY) {
    console.error('FATAL: SIDECAR_API_KEY is not set. Refusing to start.');
    process.exit(1);
}

// ---------------------------------------------------------------------
// WhatsApp client
// ---------------------------------------------------------------------
const session = {
    state: 'initializing',     // initializing | qr | authenticated | ready | disconnected | auth_failure
    phone: null,
    qrDataUrl: null,           // base64 PNG data URL while in 'qr' state
    lastError: null,
};

const puppeteerOpts = {
    args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
    ],
};
if (CHROME_PATH) {
    puppeteerOpts.executablePath = CHROME_PATH;
}

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: './.wwebjs_auth' }),
    puppeteer: puppeteerOpts,
});

client.on('qr', async (qr) => {
    session.state = 'qr';
    session.phone = null;
    try {
        session.qrDataUrl = await qrcode.toDataURL(qr, { width: 256, margin: 1 });
    } catch (err) {
        session.qrDataUrl = null;
        console.error('QR rendering failed:', err);
    }
    notifyOdoo('qr', {});
});

client.on('authenticated', () => {
    session.state = 'authenticated';
    session.qrDataUrl = null;
    notifyOdoo('authenticated', {});
});

client.on('auth_failure', (msg) => {
    session.state = 'auth_failure';
    session.lastError = msg;
    notifyOdoo('auth_failure', { error: msg });
});

client.on('ready', () => {
    session.state = 'ready';
    session.qrDataUrl = null;
    try {
        const me = client.info && client.info.wid && client.info.wid.user;
        session.phone = me ? `+${me}` : null;
    } catch (_) {
        session.phone = null;
    }
    console.log(`[wa] ready as ${session.phone || 'unknown'}`);
    notifyOdoo('ready', { phone: session.phone });
});

client.on('disconnected', (reason) => {
    session.state = 'disconnected';
    session.phone = null;
    session.lastError = reason;
    notifyOdoo('disconnected', { reason });
    console.warn('[wa] disconnected:', reason);
    scheduleRestart();
});

client.on('message', async (msg) => {
    if (!WEBHOOK_URL) return;
    try {
        await notifyOdoo('message_received', {
            message_id: msg.id && msg.id._serialized,
            from: msg.from,
            to: msg.to,
            body: msg.body,
            type: msg.type,
            timestamp: msg.timestamp,
            has_media: !!msg.hasMedia,
        });
    } catch (err) {
        console.error('[wa] webhook (incoming) failed:', err.message);
    }
});

client.on('message_ack', async (msg, ack) => {
    // ack: 1=sent, 2=delivered, 3=read, -1=failed (approx.)
    const map = { 1: 'sent', 2: 'delivered', 3: 'read', '-1': 'failed' };
    const status = map[String(ack)];
    if (!status) return;
    await notifyOdoo('message_status', {
        message_id: msg.id && msg.id._serialized,
        status,
    });
});

let isRestarting = false;
function scheduleRestart(delayMs = 5000) {
    if (isRestarting) return;
    isRestarting = true;
    session.state = 'initializing';
    session.qrDataUrl = null;
    session.phone = null;
    console.log(`[wa] scheduling restart in ${delayMs}ms...`);
    setTimeout(async () => {
        console.log('[wa] restarting client...');
        try { await client.destroy(); } catch (_) {}
        try {
            await client.initialize();
        } catch (err) {
            console.error('[wa] restart failed:', err);
            session.state = 'error';
            session.lastError = String(err);
        } finally {
            isRestarting = false;
        }
    }, delayMs);
}

console.log('[wa] initializing client...');
client.initialize().catch((err) => {
    session.state = 'error';
    session.lastError = String(err);
    console.error('[wa] initialize failed:', err);
});

// ---------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------
async function notifyOdoo(event, data) {
    if (!WEBHOOK_URL) return;
    try {
        await axios.post(
            WEBHOOK_URL,
            { jsonrpc: '2.0', method: 'call', params: { event, data } },
            { headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY }, timeout: 10000 }
        );
    } catch (err) {
        // Don't throw — webhook delivery is best-effort.
        if (err.response) {
            console.warn(`[webhook] ${event} -> ${err.response.status} ${err.response.statusText}`);
        } else {
            console.warn(`[webhook] ${event} failed: ${err.message}`);
        }
    }
}

function toJid(number) {
    const digits = String(number).replace(/[^\d]/g, '');
    if (!digits) throw new Error('Empty recipient number.');
    return `${digits}@c.us`;
}

function requireApiKey(req, res, next) {
    const provided = req.get('X-API-Key') || '';
    if (provided !== API_KEY) {
        return res.status(401).json({ ok: false, error: 'unauthorized' });
    }
    next();
}

// ---------------------------------------------------------------------
// HTTP server
// ---------------------------------------------------------------------
const app = express();
app.use(express.json({ limit: '50mb' }));

app.get('/health', (req, res) => res.json({ ok: true }));

app.use(requireApiKey);

app.get('/status', (req, res) => {
    res.json({
        state: session.state,
        phone: session.phone,
        error: session.lastError,
    });
});

app.get('/qr', (req, res) => {
    res.json({ qr: session.qrDataUrl, state: session.state });
});

app.post('/send', async (req, res) => {
    if (session.state !== 'ready') {
        return res.status(409).json({
            ok: false,
            error: `Session not ready (state=${session.state}).`,
        });
    }
    try {
        const { to, message, attachment } = req.body || {};
        if (!to) return res.status(400).json({ ok: false, error: 'Missing "to".' });

        const numberId = await client.getNumberId(toJid(to));
        if (!numberId) {
            return res.status(400).json({ ok: false, error: `Number ${to} is not on WhatsApp.` });
        }
        const jid = numberId._serialized;

        let sent;
        if (attachment && attachment.base64) {
            const media = new MessageMedia(
                attachment.mimetype || 'application/octet-stream',
                attachment.base64,
                attachment.filename || 'file'
            );
            sent = await client.sendMessage(jid, media, { caption: message || '' });
        } else {
            sent = await client.sendMessage(jid, message || '');
        }
        res.json({
            ok: true,
            message_id: sent.id && sent.id._serialized,
            to: jid,
        });
    } catch (err) {
        console.error('[send] error:', err);
        if (err.message && err.message.includes('detached Frame')) {
            session.state = 'disconnected';
            scheduleRestart();
        }
        res.status(500).json({ ok: false, error: String(err.message || err) });
    }
});

app.post('/logout', async (req, res) => {
    try {
        await client.logout();
        session.state = 'disconnected';
        session.phone = null;
        session.qrDataUrl = null;
        res.json({ ok: true });
    } catch (err) {
        res.status(500).json({ ok: false, error: String(err.message || err) });
    }
});

app.listen(PORT, HOST, () => {
    console.log(`[http] mr_whatsapp_connector sidecar listening on http://${HOST}:${PORT}`);
    if (!WEBHOOK_URL) {
        console.warn('[http] ODOO_WEBHOOK_URL not set — outbound events disabled.');
    }
});

// Graceful shutdown
async function shutdown() {
    console.log('Shutting down...');
    try { await client.destroy(); } catch (_) { /* ignore */ }
    process.exit(0);
}
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
