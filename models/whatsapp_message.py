from odoo import _, api, fields, models


class WhatsAppMessage(models.Model):
    _name = "mr.whatsapp.message"
    _description = "WhatsApp Message Log"
    _order = "create_date desc, id desc"
    _rec_name = "display_name"

    display_name = fields.Char(compute="_compute_display_name", store=True)

    direction = fields.Selection(
        [("out", "Outgoing"), ("in", "Incoming")],
        required=True,
        default="out",
        index=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("sent", "Sent"),
            ("delivered", "Delivered"),
            ("read", "Read"),
            ("failed", "Failed"),
            ("received", "Received"),
        ],
        default="draft",
        required=True,
        index=True,
    )
    number = fields.Char(string="Phone (E.164)", required=True, index=True)
    message = fields.Text()
    error = fields.Text()
    sidecar_message_id = fields.Char(string="WA Message ID", index=True)

    partner_id = fields.Many2one("res.partner", index=True, ondelete="set null")
    user_id = fields.Many2one("res.users", default=lambda s: s.env.user, ondelete="set null")

    res_model = fields.Char(string="Source Model", index=True)
    res_id = fields.Integer(string="Source Record ID", index=True)

    attachment_ids = fields.Many2many("ir.attachment", string="Attachments")

    sent_at = fields.Datetime()
    received_at = fields.Datetime()

    @api.depends("number", "direction", "create_date")
    def _compute_display_name(self):
        for rec in self:
            arrow = "→" if rec.direction == "out" else "←"
            rec.display_name = f"{arrow} {rec.number or '?'}"

    def action_open_source(self):
        self.ensure_one()
        if not (self.res_model and self.res_id):
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "view_mode": "form",
            "target": "current",
        }

    def action_resend(self):
        self.ensure_one()
        if self.direction != "out":
            return False
        Service = self.env["mr.whatsapp.service"]
        attachment = False
        if self.attachment_ids:
            attachment = self.attachment_ids[0]
        try:
            payload = Service.send_attachment_record(
                self.number, attachment, caption=self.message or ""
            ) if attachment else Service.send_message(self.number, self.message or "")
        except Exception as exc:
            self.write({"state": "failed", "error": str(exc)})
            raise
        self.write({
            "state": "sent",
            "sent_at": fields.Datetime.now(),
            "sidecar_message_id": payload.get("message_id"),
            "error": False,
        })
        return True
