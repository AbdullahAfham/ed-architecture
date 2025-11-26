from odoo import models, api


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """Create a PO from incoming email."""
        vals = {
            'partner_id': False,
            'origin': msg_dict.get('subject', 'Email RFQ'),
            'user_id': self.env.uid,
        }
        if custom_values:
            vals.update(custom_values)
        return super(PurchaseOrder, self).create(vals)

    @api.model
    def message_update(self, record, msg_dict, custom_values=None):
        """Append new emails to chatter."""
        return record.message_post(body=msg_dict.get('body', ''))
