# -*- coding: utf-8 -*-

from odoo import fields, models

class NoteInformation(models.Model):
    _name = 'bank.information'
    _description = 'Information of Bank'

    name = fields.Char(string="Name")
    desc = fields.Text(string="Description")
    qrcode_image = fields.Binary(string="Payment QR Code")
