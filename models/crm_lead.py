from odoo import _, models
from odoo.exceptions import UserError


class CrmLead(models.Model):
    _inherit = "crm.lead"

    def action_send_whatsapp(self):
        self.ensure_one()
        number =  self.phone or (self.partner_id and (self.partner_id.phone))
        if not number:
            raise UserError(_("This lead has no phone or mobile number."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Send WhatsApp Message"),
            "res_model": "mr.whatsapp.send.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_partner_id": self.partner_id.id if self.partner_id else False,
                "default_number": number,
                "default_res_model": self._name,
                "default_res_id": self.id,
            },
        }
