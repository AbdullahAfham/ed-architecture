from odoo import models, api


class ResCurrency(models.Model):
    _name = 'res.currency'
    _inherit = ['res.currency', 'pos.load.mixin']

    @api.model
    def _load_pos_data_domain(self, data):
        return [('id', 'in', [self.env.ref("base.KHR", raise_if_not_found=False).id, data['pos.config']['data'][0]['currency_id']])]
