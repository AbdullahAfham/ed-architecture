# -*- coding: utf-8 -*-
from odoo import models, fields, api


class PosConfig(models.Model):
    _inherit = "pos.config"

    # add an image field
    # the field is a binary field
    # the field is used to store the image of the QR code
    pos_khmer_name = fields.Char(string="Khmer POS Name")
    logo_image = fields.Binary(string="Logo")
    khmer_address = fields.Char(string="Khmer Address")
    phone_number = fields.Char(string="Phone")
    vat_number = fields.Char(string="VAT")
    qr_image = fields.Binary(string="QR Code")
    acc_holder_name = fields.Char(string="Account Holder Name")
