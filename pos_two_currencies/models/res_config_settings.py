# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettingsInherit(models.TransientModel):
    _inherit = 'res.config.settings'

    session_sequence_id = fields.Many2one(related='pos_config_id.session_sequence_id', readonly=False)
    pos_iface_disc_button = fields.Boolean(related='pos_config_id.iface_disc_button', readonly=False)
    pos_exchange_rate = fields.Float(related='pos_config_id.exchange_rate', readonly=False)
