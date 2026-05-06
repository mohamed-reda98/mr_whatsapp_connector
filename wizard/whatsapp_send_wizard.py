import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class WhatsAppSendWizard(models.TransientModel):
    _name = "mr.whatsapp.send.wizard"
    _description = "Compose and send a WhatsApp message"

    partner_id = fields.Many2one("res.partner")
    number = fields.Char(string="Recipient", required=True)
    country_code = fields.Char(
        string="Country Code Override",
        help="Leave empty to use the default from Settings.",
    )

    res_model = fields.Char()
    res_id = fields.Integer()

    message = fields.Text(required=True)

    attachment_ids = fields.Many2many(
        "ir.attachment",
        "mr_whatsapp_send_wizard_attachment_rel",
        "wizard_id",
        "attachment_id",
        string="Attachments",
    )

    log_to_chatter = fields.Boolean(default=True, string="Log on Source Record")

    def _source_record(self):
        if self.res_model and self.res_id and self.res_model in self.env:
            try:
                return self.env[self.res_model].browse(self.res_id).exists()
            except Exception:
                return None
        return None

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------
    def action_send(self):
        self.ensure_one()
        if not (self.message or "").strip() and not self.attachment_ids:
            raise UserError(_("Message body or at least one attachment is required."))

        Service = self.env["mr.whatsapp.service"]
        Message = self.env["mr.whatsapp.message"]

        normalized = Service._normalize_number(self.number, country_code=self.country_code or None)

        log_vals = {
            "direction": "out",
            "state": "draft",
            "number": normalized,
            "message": self.message or "",
            "partner_id": self.partner_id.id or False,
            "res_model": self.res_model or False,
            "res_id": self.res_id or 0,
            "attachment_ids": [(6, 0, self.attachment_ids.ids)],
        }
        log = Message.create(log_vals)

        try:
            attachments = list(self.attachment_ids)
            if not attachments:
                payload = Service.send_message(
                    self.number, self.message or "", country_code=self.country_code or None
                )
                last_id = payload.get("message_id")
            else:
                last_id = None
                # Send caption + first attachment in one go; remaining attachments follow.
                first = attachments[0]
                payload = Service.send_attachment_record(
                    self.number, first, caption=self.message or "",
                    country_code=self.country_code or None,
                )
                last_id = payload.get("message_id")
                for extra in attachments[1:]:
                    payload = Service.send_attachment_record(
                        self.number, extra, caption="", country_code=self.country_code or None,
                    )
                    last_id = payload.get("message_id") or last_id
        except Exception as exc:
            log.write({"state": "failed", "error": str(exc)})
            raise

        log.write({
            "state": "sent",
            "sent_at": fields.Datetime.now(),
            "sidecar_message_id": last_id,
        })

        if self.log_to_chatter:
            self._post_chatter(normalized)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("WhatsApp"),
                "message": _("Message sent to %s.") % normalized,
                "type": "success",
                "sticky": False,
            },
        }

    def _post_chatter(self, normalized):
        record = self._source_record()
        if not record:
            return
        if not hasattr(record, "message_post"):
            return
        body = _(
            "WhatsApp message sent to <b>%(num)s</b>:<br/><pre style='white-space:pre-wrap'>%(msg)s</pre>"
        ) % {"num": normalized, "msg": (self.message or "").replace("<", "&lt;")}
        try:
            record.message_post(
                body=body,
                attachment_ids=self.attachment_ids.ids,
                subtype_xmlid="mail.mt_note",
            )
        except Exception as exc:
            _logger.warning("Could not post chatter note: %s", exc)
