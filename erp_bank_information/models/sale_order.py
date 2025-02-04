# -*- coding: utf-8 -*-

from odoo import fields, models

class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    def _default_bank_information_id(self):
        note_id = self.env['bank.information'].search([], limit=1).id
        return note_id
    
    bank_information_id = fields.Many2one('bank.information', string='Note', default=_default_bank_information_id)
    sale_represent_id = fields.Many2one('hr.employee', string='Sales Rep.', store=True, tracking=True)
    input_note = fields.Text(string="Terms and Conditions")
    
    def _prepare_invoice(self):
        value = super(SaleOrderInherit, self)._prepare_invoice()
        
        value.update({
            'bank_information_id': self.bank_information_id.id if self.bank_information_id else False,
            'invoice_sale_represent_id': self.sale_represent_id.id if self.sale_represent_id else False,
            'input_narration': self.input_note or '',
        })
        return value