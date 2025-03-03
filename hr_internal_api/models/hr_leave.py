from odoo import api, fields, models


class HrLeaveInherit(models.Model):
    _inherit = 'hr.leave'

    can_approve_leave = fields.Boolean(string="Can Approve Leave", default=False)
    approve_date = fields.Datetime(string="Approve Date", store=True)

    def action_approve(self):
        super(HrLeaveInherit, self).action_approve()
        self.write({'approve_date': fields.Datetime.now()})

        return True
