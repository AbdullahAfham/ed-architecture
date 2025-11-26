from odoo import models

class PurchaseOrder(models.Model):
    _inherit = [
        'purchase.order',
        'mail.alias.mixin',
        'mail.thread',
        'mail.activity.mixin',
    ]

    def _alias_get_creation_values(self):
        values = super()._alias_get_creation_values()
        return values
