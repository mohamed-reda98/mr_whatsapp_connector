import base64
import logging

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class WhatsAppPortalController(http.Controller):

    @http.route(
        "/whatsapp/send",
        auth="user",
        type="http",
        methods=["GET"],
        website=True,
        sitemap=False,
    )
    def portal_form(self, **kwargs):
        return request.render("mr_whatsapp_connector.portal_send_form", {})

    @http.route(
        "/whatsapp/send",
        auth="user",
        type="http",
        methods=["POST"],
        website=True,
        csrf=False,
        sitemap=False,
    )
    def portal_send(self, **kwargs):
        number = (kwargs.get("number") or "").strip()
        country_code = (kwargs.get("country_code") or "").strip().lstrip("+")
        message = (kwargs.get("message") or "").strip()
        uploaded = request.httprequest.files.getlist("attachments")
        files = [f for f in uploaded if f and f.filename]

        if not number:
            return request.render("mr_whatsapp_connector.portal_send_form", {
                "error": "Phone number is required.",
                "number": number,
                "country_code": country_code,
                "message": message,
            })

        Service = request.env["mr.whatsapp.service"].sudo()
        Message = request.env["mr.whatsapp.message"].sudo()

        try:
            normalized = Service._normalize_number(number, country_code=country_code or None)

            last_id = None
            if not files:
                payload = Service.send_message(normalized, message, country_code=country_code or None)
                last_id = payload.get("message_id")
            else:
                first = files[0]
                first_data = base64.b64encode(first.read()).decode()
                payload = Service.send_message(normalized, message, attachment={
                    "filename": first.filename,
                    "mimetype": first.mimetype or "application/octet-stream",
                    "base64": first_data,
                }, country_code=country_code or None)
                last_id = payload.get("message_id")
                for f in files[1:]:
                    fdata = base64.b64encode(f.read()).decode()
                    p = Service.send_message(normalized, "", attachment={
                        "filename": f.filename,
                        "mimetype": f.mimetype or "application/octet-stream",
                        "base64": fdata,
                    }, country_code=country_code or None)
                    last_id = p.get("message_id") or last_id

            Message.create({
                "direction": "out",
                "state": "sent",
                "number": normalized,
                "message": message,
                "sidecar_message_id": last_id,
                "sent_at": fields.Datetime.now(),
                "user_id": request.env.uid,
            })

            return request.render("mr_whatsapp_connector.portal_send_form", {
                "success": True,
                "sent_to": normalized,
            })

        except Exception as exc:
            _logger.error("Portal WhatsApp send failed for %r: %s", number, exc)
            return request.render("mr_whatsapp_connector.portal_send_form", {
                "error": str(exc),
                "number": number,
                "country_code": country_code,
                "message": message,
            })
