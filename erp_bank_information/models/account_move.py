# -*- coding: utf-8 -*-

from odoo import fields, models

class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    def _default_bank_information_id(self):
        note_id = self.env['bank.information'].search([], limit=1).id
        return note_id
    
    bank_information_id = fields.Many2one('bank.information', string='Note', default=_default_bank_information_id)
    invoice_sale_represent_id = fields.Many2one('hr.employee', string="Sales Rep.", store=True, readonly=False, tracking=True)
    input_narration = fields.Text(string="Terms and Conditions")
