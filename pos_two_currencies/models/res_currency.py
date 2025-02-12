from odoo import models, api


class ResCurrency(models.Model):
    _name = 'res.currency'
    _inherit = ['res.currency', 'pos.load.mixin']

    @api.model
    def _load_pos_data_domain(self, data):
        return [('id', 'in', [data['pos.config']['data'][0]['currency_id'], self.env.ref("base.KHR", raise_if_not_found=False).id])]

    # override Mixin method for sorting by name
    def _load_pos_data(self, data):
        domain = self._load_pos_data_domain(data)
        fields = self._load_pos_data_fields(data['pos.config']['data'][0]['id'])
        return {
            'data': self.search_read(domain, fields, load=False, order="name desc") if domain is not False else [],
            'fields': fields,
        }
