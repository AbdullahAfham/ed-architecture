from odoo import models

class PurchaseOrder(models.Model):
    _inherit = ['purchase.order', 'mail.alias.mixin']

    # REQUIRED: this method tells Odoo which field stores the alias.
    def _get_alias_model_name(self, vals):
        return 'purchase.order'

    # REQUIRED: store alias record
    def _get_alias_domain(self):
        return None

    # REQUIRED: how to create PO from email
    @classmethod
    def _alias_get_fields(cls):
        return ['partner_id', 'date_order', 'origin', 'user_id']

    # REQUIRED: default values when PO created from email
    def _alias_get_creation_values(self):
        return {
            'partner_id': False,
            'user_id': self.env.uid,
        }
