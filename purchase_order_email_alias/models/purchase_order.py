from odoo import models

class PurchaseOrder(models.Model):
    _inherit = ['purchase.order', 'mail.alias.mixin']

    def _alias_get_creation_values(self):
        # When PO is created from email, you can set default values here
        values = super()._alias_get_creation_values()
        return values
