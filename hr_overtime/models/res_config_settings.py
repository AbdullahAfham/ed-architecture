from odoo import fields, models, api


class OvertimeSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    is_batch = fields.Boolean(string="Enable Batch Overtime")

    @api.model
    def get_values(self):
        res = super(OvertimeSettings, self).get_values()
        is_batch_value = self.env['ir.config_parameter'].sudo().get_param('hr_overtime.is_batch', default=False)
        res.update(
            is_batch=is_batch_value
        )
        return res
    
    def set_values(self):
        super(OvertimeSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('hr_overtime.is_batch', self.is_batch)

        batch_overtime_group = self.env.ref('hr_overtime.group_batch_overtime_user')

        internal_users = self.env['res.users'].search([
            ('groups_id', 'in', [self.env.ref('base.group_user').id]),
            ('active', '=', True) 
        ])

        if self.is_batch:
            for user in internal_users:
                batch_overtime_group.write({'users': [(4, user.id)]})
        else:
            for user in internal_users:
                batch_overtime_group.write({'users': [(3, user.id)]})