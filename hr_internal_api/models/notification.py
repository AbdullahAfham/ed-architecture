from odoo import models, fields


class Notification(models.Model):
    _name = 'mobile.notification'
    _description = 'Mobile Notification'

    title = fields.Char(string='Title')
    message = fields.Char(string='Message')
    user_id = fields.Many2one('res.users', string='User')
    is_read = fields.Boolean(string='Is Read', default=False)
    link = fields.Char(string='Link', help='Used to redirect to the record in mobile')
