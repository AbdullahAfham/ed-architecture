from odoo import models, fields, api, _


class BlacklistToken(models.Model):
    _name = 'blacklist.token'
    _description = 'Blacklist Token'

    token = fields.Char(string='Token', required=True)
    user_id = fields.Many2one('res.users', string='User', required=True)
    blacklisted_at = fields.Datetime(string='Blacklisted On', required=True, default=fields.Datetime.now())

    @api.model
    def check_token(self, token):
        token = self.search([('token', '=', token)])
        if token:
            return True
        return False

    @api.model
    def remove_blacklist_token(self, token):
        token = self.search([('token', '=', token)])
        if token:
            token.is_blacklisted = False
            return True
        return False
