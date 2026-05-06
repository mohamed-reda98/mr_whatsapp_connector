import base64
import logging
import re

import requests

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PARAM_SIDECAR_URL = "mr_whatsapp_connector.sidecar_url"
PARAM_API_KEY = "mr_whatsapp_connector.api_key"
PARAM_DEFAULT_COUNTRY = "mr_whatsapp_connector.default_country_code"
PARAM_LOG_INCOMING = "mr_whatsapp_connector.log_incoming"
DEFAULT_TIMEOUT = 20


class WhatsAppService(models.AbstractModel):
    """Thin client around the Node.js whatsapp-web.js sidecar."""

    _name = "mr.whatsapp.service"
    _description = "WhatsApp Sidecar Client"

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------
    @api.model
    def _get_config(self):
        ICP = self.env["ir.config_parameter"].sudo()
        url = (ICP.get_param(PARAM_SIDECAR_URL) or "").rstrip("/")
        api_key = ICP.get_param(PARAM_API_KEY) or ""
        country = (ICP.get_param(PARAM_DEFAULT_COUNTRY) or "").strip()
        return {
            "url": url,
            "api_key": api_key,
            "country": country,
            "log_incoming": ICP.get_param(PARAM_LOG_INCOMING) == "True",
        }

    @api.model
    def _headers(self, api_key):
        return {
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        }

    # ------------------------------------------------------------------
    # Phone normalization
    # ------------------------------------------------------------------
    @api.model
    def _normalize_number(self, number, country_code=None):
        """Return digits-only E.164-style number (no +).

        whatsapp-web.js wants the JID as digits + '@c.us'. We pass digits
        only and let the sidecar build the JID.
        """
        if not number:
            raise UserError(_("Recipient phone number is empty."))
        cfg = self._get_config()
        cc = (country_code or cfg["country"] or "").strip().lstrip("+")
        cleaned = re.sub(r"[^\d+]", "", number)
        if cleaned.startswith("+"):
            cleaned = cleaned[1:]
        elif cleaned.startswith("00"):
            cleaned = cleaned[2:]
        elif cc and not cleaned.startswith(cc):
            # Heuristic: assume the local portion lacks the country prefix.
            cleaned = cc + cleaned.lstrip("0")
        if not cleaned.isdigit() or len(cleaned) < 6:
            raise UserError(_("Phone number %r does not look valid.") % number)
        return cleaned

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    @api.model
    def _request(self, method, path, **kwargs):
        cfg = self._get_config()
        if not cfg["url"]:
            raise UserError(_("WhatsApp sidecar URL is not configured. Go to Settings → WhatsApp."))
        timeout = kwargs.pop("timeout", DEFAULT_TIMEOUT)
        try:
            resp = requests.request(
                method,
                f"{cfg['url']}{path}",
                headers=self._headers(cfg["api_key"]),
                timeout=timeout,
                **kwargs,
            )
        except requests.exceptions.ConnectionError as exc:
            raise UserError(_("Cannot reach WhatsApp sidecar at %s.\n%s") % (cfg["url"], exc))
        except requests.exceptions.Timeout:
            raise UserError(_("WhatsApp sidecar timed out (%ss).") % timeout)
        if resp.status_code == 401:
            raise UserError(_("Sidecar rejected the API key. Check Settings → WhatsApp."))
        if resp.status_code >= 400:
            raise UserError(_("Sidecar error %s: %s") % (resp.status_code, resp.text[:500]))
        try:
            return resp.json()
        except ValueError:
            return {"raw": resp.text}

    # ------------------------------------------------------------------
    # Public sidecar operations
    # ------------------------------------------------------------------
    @api.model
    def get_status(self):
        """Returns dict: {state, phone, qr (base64 png or None), ...}"""
        try:
            return self._request("GET", "/status")
        except UserError as exc:
            return {"state": "error", "error": str(exc)}

    @api.model
    def get_qr(self):
        try:
            return self._request("GET", "/qr")
        except UserError as exc:
            return {"qr": None, "error": str(exc)}

    @api.model
    def logout(self):
        return self._request("POST", "/logout")

    @api.model
    def send_message(self, number, message, attachment=None, country_code=None):
        """Send a WhatsApp message via the sidecar.

        attachment: optional dict {filename, mimetype, base64}.
        Returns the sidecar payload, including 'message_id'.
        """
        to = self._normalize_number(number, country_code=country_code)
        payload = {"to": to, "message": message or ""}
        if attachment:
            payload["attachment"] = {
                "filename": attachment.get("filename") or "file",
                "mimetype": attachment.get("mimetype") or "application/octet-stream",
                "base64": attachment["base64"],
            }
        return self._request("POST", "/send", json=payload, timeout=60)

    @api.model
    def send_attachment_record(self, number, attachment_record, caption=None, country_code=None):
        if not attachment_record:
            return self.send_message(number, caption or "", country_code=country_code)
        data = attachment_record.datas
        if isinstance(data, bytes):
            data = data.decode()
        return self.send_message(
            number,
            caption or "",
            attachment={
                "filename": attachment_record.name,
                "mimetype": attachment_record.mimetype or "application/octet-stream",
                "base64": data,
            },
            country_code=country_code,
        )
