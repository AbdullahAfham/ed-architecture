from odoo import _, api, fields, models
from odoo.addons.hr_internal_api.controller.send_notification import send_notification


class HrAnnouncement(models.Model):
    _name = "hr.announcement"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string='Reference', copy=False)
    title = fields.Char(
        string='Title', required=True
    )
    image = fields.Binary(
        string='Image'
    )
    description = fields.Text(
        string='Description'
    )
    date_release = fields.Datetime(
        string='Release Date', required=True,
        default=lambda self: fields.Datetime.now()
    )
    state = fields.Selection([
        ('draft', 'Draft'), 
        ('release', 'Released'), 
        ('cancel', 'Cancelled')], string='Status', default='draft'
    )
    is_editable = fields.Boolean(
        compute='_compute_is_editable', string='Editable', default=True
    )

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('hr.announcement') or 'New'
        
        return super(HrAnnouncement, self).create(vals)

    @api.depends('state')
    def _compute_is_editable(self):
        if self.state in ('release', 'cancel'):
            self.is_editable = False
        else: 
            self.is_editable = True

    def action_release(self):
        self.ensure_one()

        # get all employee from payslip run
        employee_ids = self.env['hr.employee'].search([('user_id.device_token', '!=', False)])

        for employee_id in employee_ids:
            send_notification(
                title=self.title or '',
                body=self.description or '',
                device_token=employee_id.user_id.device_token,
                user_id=employee_id.user_id.id,
                link='/news/%s' % (self.id),
            )

        return self.write({'state': 'release'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})
