from odoo import _, api, fields, models
from odoo.exceptions import UserError


class WhatsAppTemplate(models.Model):
    _name = "mr.whatsapp.template"
    _description = "WhatsApp Message Template"
    _inherit = ["mail.render.mixin"]
    _order = "name"

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    model_id = fields.Many2one(
        "ir.model",
        string="Applies to",
        required=True,
        ondelete="cascade",
        domain=[("transient", "=", False)],
    )
    model = fields.Char(related="model_id.model", store=True, index=True, readonly=True)
    body = fields.Text(
        required=True,
        translate=True,
        help="Inline template syntax. Example: Hello {{ object.name }}, your order total is "
             "{{ object.amount_total }}.",
    )
    phone_field = fields.Char(
        string="Phone Field",
        help="Field on the target record holding the phone number. "
             "Defaults to mobile then phone if blank.",
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        string="Static Attachments",
        help="Files attached to every message generated from this template.",
    )
    report_id = fields.Many2one(
        "ir.actions.report",
        string="Generated Report",
        help="Optional report to render and attach when sending (PDF).",
    )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _render_body(self, res_ids):
        """Render `body` against res_ids using the inline_template engine.

        Returns dict {res_id: rendered_text}.
        """
        self.ensure_one()
        return self._render_template(
            self.body,
            self.model,
            res_ids,
            engine="inline_template",
        )

    def render_for_record(self, record):
        """Convenience: render body for a single record. Returns string."""
        self.ensure_one()
        if record._name != self.model:
            raise UserError(_(
                "Template %(tpl)s is for model %(tmodel)s, not %(rmodel)s."
            ) % {"tpl": self.name, "tmodel": self.model, "rmodel": record._name})
        rendered = self._render_body(record.ids)
        return rendered.get(record.id, "")

    # ------------------------------------------------------------------
    # Phone resolution
    # ------------------------------------------------------------------
    def _resolve_phone(self, record):
        """Return the phone string from a record, following template config."""
        self.ensure_one()
        if record._name != self.model:
            return None
        candidates = []
        if self.phone_field:
            candidates.append(self.phone_field)
        candidates.extend(["mobile", "phone", "partner_id.mobile", "partner_id.phone"])
        for path in candidates:
            try:
                value = record.mapped(path)
            except Exception:
                continue
            if value and value[0]:
                return value[0]
        return None

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains("body")
    def _check_body(self):
        for tpl in self:
            if not (tpl.body or "").strip():
                raise UserError(_("Template body cannot be empty."))
