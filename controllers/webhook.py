import hmac
import logging

from odoo import _, fields, http
from odoo.http import request

from ..models.whatsapp_config import (
    PARAM_API_KEY,
    PARAM_LOG_INCOMING,
)

_logger = logging.getLogger(__name__)


class WhatsAppWebhookController(http.Controller):
    """Endpoints called by the Node.js sidecar (inbound) and by the Odoo UI (QR/status)."""

    def _check_auth(self):
        ICP = request.env["ir.config_parameter"].sudo()
        expected = ICP.get_param(PARAM_API_KEY) or ""
        provided = request.httprequest.headers.get("X-API-Key", "")
        if not expected or not hmac.compare_digest(expected, provided):
            return False
        return True

    # ------------------------------------------------------------------
    # Sidecar -> Odoo
    # ------------------------------------------------------------------
    @http.route(
        "/mr_whatsapp/webhook",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def webhook(self, event=None, data=None, **kwargs):
        if not self._check_auth():
            return {"ok": False, "error": "unauthorized"}

        data = data or {}
        env = request.env(su=True)

        if event == "message_status":
            return self._handle_status(env, data)
        if event == "message_received":
            return self._handle_incoming(env, data)
        if event in ("ready", "authenticated", "qr", "disconnected", "auth_failure"):
            _logger.info("WhatsApp sidecar event: %s", event)
            return {"ok": True}

        _logger.info("Unknown WhatsApp webhook event: %r", event)
        return {"ok": True, "ignored": True}

    def _handle_status(self, env, data):
        msg_id = data.get("message_id")
        new_state = data.get("status")  # sent, delivered, read, failed
        if not msg_id or not new_state:
            return {"ok": True, "ignored": True}
        rec = env["mr.whatsapp.message"].search([("sidecar_message_id", "=", msg_id)], limit=1)
        if rec and new_state in {"sent", "delivered", "read", "failed"}:
            vals = {"state": new_state}
            if new_state == "failed":
                vals["error"] = data.get("error") or _("Sidecar reported failure.")
            rec.write(vals)
        return {"ok": True}

    def _handle_incoming(self, env, data):
        if env["ir.config_parameter"].get_param(PARAM_LOG_INCOMING) != "True":
            return {"ok": True, "ignored": "logging_disabled"}

        number = (data.get("from") or "").split("@")[0]
        body = data.get("body") or ""
        message_id = data.get("message_id")

        partner = env["res.partner"].search(
            [("phone", "=like", "%" + number[-9:])],
            limit=1,
        )

        env["mr.whatsapp.message"].create({
            "direction": "in",
            "state": "received",
            "number": number,
            "message": body,
            "sidecar_message_id": message_id,
            "partner_id": partner.id if partner else False,
            "received_at": fields.Datetime.now(),
        })
        return {"ok": True}

    # ------------------------------------------------------------------
    # Odoo UI -> proxy to sidecar (avoids CORS, hides API key)
    # ------------------------------------------------------------------
    @http.route(
        "/mr_whatsapp/status",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def status(self, **kwargs):
        if not request.env.user.has_group("base.group_system"):
            return {"state": "forbidden"}
        return request.env["mr.whatsapp.service"].sudo().get_status()

    @http.route(
        "/mr_whatsapp/qr",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def qr(self, **kwargs):
        if not request.env.user.has_group("base.group_system"):
            return {"qr": None, "error": "forbidden"}
        return request.env["mr.whatsapp.service"].sudo().get_qr()

    @http.route(
        "/mr_whatsapp/logout",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def logout(self, **kwargs):
        if not request.env.user.has_group("base.group_system"):
            return {"ok": False, "error": "forbidden"}
        try:
            request.env["mr.whatsapp.service"].sudo().logout()
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
