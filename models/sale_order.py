from odoo import _, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_send_whatsapp(self):
        self.ensure_one()
        partner = self.partner_id
        number = partner.phone
        if not number:
            raise UserError(_("%s has no phone or mobile number.") % partner.display_name)
        return {
            "type": "ir.actions.act_window",
            "name": _("Send WhatsApp Message"),
            "res_model": "mr.whatsapp.send.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_partner_id": partner.id,
                "default_number": number,
                "default_res_model": self._name,
                "default_res_id": self.id,
            },
        }
