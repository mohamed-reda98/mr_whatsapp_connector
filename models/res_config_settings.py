from odoo import api, fields, models

from .whatsapp_config import (
    PARAM_API_KEY,
    PARAM_DEFAULT_COUNTRY,
    PARAM_LOG_INCOMING,
    PARAM_SIDECAR_URL,
)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    whatsapp_sidecar_url = fields.Char(
        string="Sidecar URL",
        config_parameter=PARAM_SIDECAR_URL,
        default="http://localhost:3000",
        help="Base URL of the whatsapp-web.js sidecar service.",
    )
    whatsapp_api_key = fields.Char(
        string="Sidecar API Key",
        config_parameter=PARAM_API_KEY,
        help="Shared secret. Must match SIDECAR_API_KEY in the sidecar's environment.",
    )
    whatsapp_default_country_code = fields.Char(
        string="Default Country Code",
        config_parameter=PARAM_DEFAULT_COUNTRY,
        help="Used to prefix local numbers without a country code (e.g. 20 for Egypt).",
    )
    whatsapp_log_incoming = fields.Boolean(
        string="Log Incoming Messages",
        config_parameter=PARAM_LOG_INCOMING,
        help="When enabled, the sidecar webhook stores received messages.",
    )

    # Live status (read-only, refreshed by the QR widget).
    whatsapp_status_state = fields.Char(string="Status", readonly=True, default="unknown")
    whatsapp_status_phone = fields.Char(string="Paired Number", readonly=True)

    @api.model
    def get_values(self):
        res = super().get_values()
        status = self.env["mr.whatsapp.service"].sudo().get_status()
        res["whatsapp_status_state"] = status.get("state", "unknown")
        res["whatsapp_status_phone"] = status.get("phone") or ""
        return res

    def action_whatsapp_logout(self):
        self.env["mr.whatsapp.service"].sudo().logout()
        return True

    def action_whatsapp_refresh(self):
        return {"type": "ir.actions.client", "tag": "reload"}
