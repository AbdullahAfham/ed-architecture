# -*- coding: utf-8 -*-

from odoo import fields, models

class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    def _prepare_confirmation_values(self):
        """ Override to remove 'date_order' from confirmation values. """
        res = super(SaleOrderInherit, self)._prepare_confirmation_values()

        res.pop('date_order', None)
        return res