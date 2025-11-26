from odoo import models

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # Add alias support safely
    _mail_alias = True

    def _alias_get_creation_values(self):
        return super(PurchaseOrder, self)._alias_get_creation_values()
