# -*- coding: utf-8 -*-

from odoo import fields, models

class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    def _default_bank_information_id(self):
        note_id = self.env['bank.information'].search([], limit=1).id
        return note_id
    
    bank_information_id = fields.Many2one('bank.information', string='Note', default=_default_bank_information_id)

    def _prepare_invoice(self):
        invoice_vals = super(SaleOrderInherit, self)._prepare_invoice()
        
        invoice_vals['bank_information_id'] = self.bank_information_id.id
        return invoice_vals