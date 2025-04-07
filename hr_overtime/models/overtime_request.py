# -*- coding: utf-8 -*-

from dateutil import relativedelta
import pandas as pd
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.resource.models.utils import HOURS_PER_DAY


class HrOverTime(models.Model):
    _name = 'hr.overtime'
    _description = "HR Overtime"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    def _get_employee_domain(self):
        employee = self.env['hr.employee'].search(
            [('user_id', '=', self.env.user.id)], limit=1)
        domain = [('id', '=', employee.id)]
        if self.env.user.has_group('hr.group_hr_user'):
            domain = []
        print(domain)
        return domain

    def _default_employee(self):
        return self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)

    @api.onchange('days_no_tmp')
    def _onchange_days_no_tmp(self):
        self.days_no = self.days_no_tmp

    name = fields.Char('Name', readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', domain=_get_employee_domain, default=lambda self: self.env.user.employee_id.id, required=True)
    department_id = fields.Many2one('hr.department', string="Department", related="employee_id.department_id")
    job_id = fields.Many2one('hr.job', string="Job", related="employee_id.job_id")
    manager_id = fields.Many2one('res.users', string="Manager", store=True)
    user_id = fields.Many2one('res.users', string="User", default=lambda self: self.env.uid, store=True)
    # display if is_batch == True
    batch_id = fields.Many2one('hr.batch.overtime', string="Batch")
    submitter_ids = fields.Many2many('res.users', string="Submitters", related="batch_id.creator_list")
    current_user_boolean = fields.Boolean()
    project_id = fields.Many2one('project.project', string="Project", related="batch_id.project_id", store=True)
    project_manager_id = fields.Many2one('res.users', string="Manager", store=True)
    hr_officer_id = fields.Many2one('res.users', string="HR Manager", compute="_get_approvers", store=True)
    om_approver_id = fields.Many2one('res.users', string="Operation Manager", compute="_get_approvers", store=True)
    contract_id = fields.Many2one('hr.contract', string="Contract", related="employee_id.contract_id",)
    date_from = fields.Datetime('Date From', store=True)
    date_to = fields.Datetime('Date to', store=True)

    scan_ot_in = fields.Datetime(string="OT IN", readonly="False", store=True)
    scan_ot_out = fields.Datetime(string="OT OUT", readonly="False", store=True)
    actual_duration = fields.Float(string="Actual Duration",  compute="_compute_actual_duration",)
    balance = fields.Float(string="Balance",compute="_compute_balance")
    break_hours = fields.Float('Break Time', store=True)
    days_no_tmp = fields.Float('Hours', compute="_get_days", store=True)
    days_no = fields.Float('No. of Days', store=True)
    desc = fields.Text('Description', store=True)
    state = fields.Selection([('draft', 'Draft'),
                              ('approval', 'Waiting'),
                              ('officer_approval', 'Manager Approved'),
                              ('finance_approval', 'HR Validated'),
                              ('approved', 'Approved'),
                              ('refused', 'Refused')],
                             # related="batch_id.state",
                             store=True, string="State", tracking=True, default="draft")
    cancel_reason = fields.Text('Refuse Reason')
    leave_id = fields.Many2one('hr.leave.allocation', string="Leave ID")
    attchd_copy = fields.Binary('Attach A File')
    attchd_copy_name = fields.Char('File Name')
    type = fields.Selection([('cash', 'Cash'), ('leave', 'leave')], default="cash", required=True, string="Type")
    # remove related from batch_id, we will compute it instaed if is_batch is True
    overtime_type_id = fields.Many2one('overtime.type', store=True)
    public_holiday = fields.Char(string='Public Holiday', readonly=True)
    attendance_ids = fields.Many2many('hr.attendance', string='Attendance')
    work_schedule = fields.One2many(related='employee_id.resource_calendar_id.attendance_ids')
    global_leaves = fields.One2many(related='employee_id.resource_calendar_id.global_leave_ids')
    duration_type = fields.Selection([('hours', 'Hour'), ('days', 'Days')], string="Duration Type", default="hours", required=True)
    cash_hrs_amount = fields.Float(string='Overtime Amount')
    cash_day_amount = fields.Float(string='Overtime Amount')
    payslip_paid = fields.Boolean('Paid in Payslip', readonly=True)
    approver_id = fields.Many2one('res.users', string='Approver')
    company_id = fields.Many2one('res.company', string='Company', readonly=True, copy=False, help="Company", default=lambda self: self.env['res.company']._company_default_get(), states={'draft': [('readonly', False)]})
    payslip_id = fields.Many2one('hr.payslip', string="Payslip", readonly=True)

    @api.depends('batch_id')
    def _compute_batch_info(self):
        print("=== compute_Date ===")
        """Set dates based on the linked batch."""
        for rec in self:
            rec.date_from = rec.batch_id.date_from if rec.batch_id else False
            rec.date_to = rec.batch_id.date_to if rec.batch_id else False
            rec.overtime_type_id = rec.batch_id.overtime_type_id.id if rec.batch_id else False
            print(f"=== type: {rec.overtime_type_id}, batch: {rec.batch_id.overtime_type_id.id}")

    def set_to_paid(self):
        self.sudo().write({'payslip_paid': True})

    @api.depends('user_id')
    def check_user_id(self):
        for i in self:
            if self.env.user.id == self.employee_id.user_id.id:
                i.update({
                    'current_user_boolean': True,
                })

    @api.onchange('employee_id')
    def _get_defaults(self):
        for sheet in self:
            if sheet.employee_id:
                sheet.update({
                    'department_id': sheet.employee_id.department_id.id,
                    'job_id': sheet.employee_id.job_id.id,
                    'project_manager_id': sheet.sudo().employee_id.parent_id.user_id.id,
                })

    @api.depends('batch_id', 'batch_id.approver_id', 'batch_id.hr_officer_approver_id', 'batch_id.om_approver_id')
    def _get_approvers(self):
        for sheet in self:
            if sheet.batch_id:
                sheet.project_manager_id = sheet.batch_id.approver_id.id
                sheet.hr_officer_id = sheet.batch_id.hr_officer_approver_id.id
                sheet.om_approver_id = sheet.batch_id.om_approver_id.id

    @api.depends('duration_type', 'date_from', 'date_to', 'break_hours')
    def _get_days(self):
        for recd in self:
            if recd.date_from and recd.date_to:
                if recd.date_from > recd.date_to:
                    raise ValidationError('Start Date must be less than End Date')
        for sheet in self:
            if sheet.date_from and sheet.date_to:
                start_dt = fields.Datetime.from_string(sheet.date_from)
                finish_dt = fields.Datetime.from_string(sheet.date_to)
                s = finish_dt - start_dt
                difference = relativedelta.relativedelta(finish_dt, start_dt)
                hours = difference.hours
                minutes = difference.minutes
                days_in_mins = s.days * 24 * 60
                hours_in_mins = hours * 60
                hours = ((days_in_mins + hours_in_mins + minutes) / 60)
                duration = hours - sheet.break_hours
                days_no = duration / 24
                sheet.days_no_tmp = duration if sheet.duration_type == 'hours' else days_no
            else:
                sheet.days_no_tmp = 0

    @api.depends('break_hours','scan_ot_in','scan_ot_out')
    def _compute_actual_duration(self):
        # for recd in self:
        #     if recd.scan_ot_in and recd.scan_ot_out:
        #         if recd.scan_ot_in > recd.scan_ot_out:
        #             raise ValidationError('Start Date must be less than End Date')
        for sheet in self:
            if sheet.scan_ot_in and sheet.scan_ot_out:
                start_dt = fields.Datetime.from_string(sheet.scan_ot_in)
                finish_dt = fields.Datetime.from_string(sheet.scan_ot_out)
                s = finish_dt - start_dt
                difference = relativedelta.relativedelta(finish_dt, start_dt)
                hours = difference.hours
                minutes = difference.minutes
                days_in_mins = s.days * 24 * 60
                hours_in_mins = hours * 60
                hours = ((days_in_mins + hours_in_mins + minutes) / 60)
                duration = hours - sheet.break_hours
                days_no = duration / 24
                sheet.actual_duration = duration if sheet.duration_type == 'hours' else days_no
            else:
                sheet.actual_duration = 0

    @api.depends('actual_duration', 'days_no_tmp')
    def _compute_balance(self):
        for ot in self:
            ot.balance = ot.actual_duration - ot.days_no_tmp


    @api.onchange('overtime_type_id')
    def _get_hour_amount(self):
        duration = self.actual_duration or self.days_no_tmp
        if self.actual_duration and self.actual_duration > self.days_no_tmp:
            duration = self.days_no_tmp
        if self.actual_duration and self.actual_duration < self.days_no_tmp:
            duration = self.actual_duration
        if self.actual_duration < 0.0:
            duration = self.days_no_tmp

            
            # Get a rule of Overtime Type which satisfied the condition
            # rule_line_ids = self.overtime_type_id.rule_line_ids.filtered(lambda r: r.from_hrs <= duration <= r.to_hrs)

            # Get a duration correspond to the rule, or 0.0 will be given
            # hrs_amount = rule_line_ids.hrs_amount if rule_line_ids else 0.0

        self.cash_hrs_amount = self.contract_id.over_hour * self.overtime_type_id.coefficient * duration


    def submit_request(self):
        return self.sudo().write({
            'state': 'approval',
        })

    def approve(self):
        return self.sudo().write({
            'state': 'officer_approval',
        })

    def submit_to_finance(self):
        return self.sudo().write({
            'state': 'finance_approval',
        })

    def finance_approve(self):
        return self.sudo().write({
            'state': 'approved',
        })

    def reject(self):
        return self.sudo().write({
            'state': 'refused',
        })

    def action_draft(self):
        return self.sudo().write({
            'state': 'draft',
            'cash_hrs_amount': 0,
            'cash_day_amount': 0,
            'overtime_type_id': False,
        })

    def action_reset_to_approval(self):
        return self.sudo().write({
            'state': 'approval',
        })

    def action_reset_to_officer_approval(self):
        return self.sudo().write({
            'state': 'officer_approval',
        })

    def action_reset_to_finance_approval(self):
        return self.sudo().write({
            'state': 'finance_approval',
        })

    @api.constrains('date_from', 'date_to')
    def _check_date(self):
        for req in self:
            domain = [
                ('date_from', '<=', req.date_to),
                ('date_to', '>=', req.date_from),
                ('employee_id', '=', req.employee_id.id),
                ('id', '!=', req.id),
                ('state', 'not in', ['refused']),
            ]
            nholidays = self.search_count(domain)
            if nholidays:
                raise ValidationError(_(
                    'You can not have 2 Overtime requests that overlaps on same day!'))

    @api.model
    def create(self, values):
        seq = self.env['ir.sequence'].next_by_code('hr.overtime') or '/'
        values['name'] = seq
        return super(HrOverTime, self.sudo()).create(values)

    def unlink(self):
        for overtime in self.filtered(lambda overtime: overtime.state not in ['draft', 'approval', 'officer_approval']):
            raise UserError(_('You cannot delete TIL request which is not in draft state.'))
        
        return super(HrOverTime, self).unlink()

    @api.onchange('date_from', 'date_to', 'employee_id')
    def _onchange_date(self):
        holiday = False
        if self.contract_id and self.employee_id and self.date_from and self.date_to:
            for leaves in self.employee_id.resource_calendar_id.global_leave_ids:
                leave_dates = pd.date_range(leaves.date_from, leaves.date_to).date
                overtime_dates = pd.date_range(self.date_from, self.date_to).date

                for over_time in overtime_dates:
                    for leave_date in leave_dates:
                        if leave_date == over_time:
                            holiday = True
            if holiday:
                self.write({
                    'public_holiday': 'You have Public Holidays in your Overtime request.'})
            else:
                self.write({'public_holiday': ' '})
            hr_attendance = self.env['hr.attendance'].search(
                [('check_in', '>=', self.date_from),
                 ('check_in', '<=', self.date_to),
                 ('employee_id', '=', self.employee_id.id)])
            self.update({
                'attendance_ids': [(6, 0, hr_attendance.ids)]
            })

    def get_attendance_overtime(self):

        for rec in self:
            attendance_ot_id = self.env['overtime.attendance'].search(
                [('name', '=', rec.employee_id.id), ('ot_date', '=', rec.date_from.date())], limit=1)
            rec.scan_ot_in = attendance_ot_id.ot_in
            rec.scan_ot_out = attendance_ot_id.ot_out
            # print("=========", attendance_ot_id)
        return True

    def activity_update(self):
        to_clean, to_do = self.env['hr.overtime'], self.env['hr.overtime']
        for overtime in self:
            # start = UTC.localize(holiday.date_from).astimezone(timezone(holiday.employee_id.tz or 'UTC'))
            # end = UTC.localize(holiday.date_to).astimezone(timezone(holiday.employee_id.tz or 'UTC'))
            note = _(
                'You have a Overtime Request to Approve from %(name)s',
                    name=overtime.user_id.name
            )
            if overtime.state == 'draft':
                overtime.activity_schedule(
                    'hr_overtime.mail_act_hr_overtime',
                    note=note,
                    user_id=overtime.sudo().approver_id.id or self.env.user.id)
            elif overtime.state == 'approval':
                overtime.activity_schedule(
                    'hr_overtime.mail_act_hr_overtime',
                    note=note,
                    user_id=overtime.sudo().approver_id.id or self.env.user.id)
            elif overtime.state == 'officer_approval':
                overtime.activity_schedule(
                    'hr_overtime.mail_act_hr_overtime',
                    note=note,
                    user_id=overtime.sudo().approver_id.id or self.env.user.id)
            elif overtime.state == 'finance_approval':
                overtime.activity_schedule(
                    'hr_overtime.mail_act_hr_overtime',
                    note=note,
                    user_id=overtime.sudo().approver_id.id or self.env.user.id)
            elif overtime.state == 'approved':
                overtime.activity_schedule(
                    'hr_overtime.mail_act_hr_overtime',
                    note=note,
                    user_id=overtime.sudo().approver_id.id or self.env.user.id)
            elif overtime.state == 'rejected':
                overtime.activity_schedule(
                    'purchase_request_approval.mail_act_purchase_request',
                    note=_('Your Purchase Request have been Rejected'),
                    user_id=overtime.user_id.id or self.env.user.id)
        # if to_clean:
        #     to_clean.activity_unlink(['hr_holidays.mail_act_leave_approval', 'hr_holidays.mail_act_leave_second_approval'])
        # if to_do:
        #     to_do.activity_feedback(['hr_holidays.mail_act_leave_approval', 'hr_holidays.mail_act_leave_second_approval'])



class HrOverTimeType(models.Model):
    _name = 'overtime.type'
    _description = "HR Overtime Type"

    name = fields.Char('Name')
    type = fields.Selection([('cash', 'Cash'),
                             ('leave', 'Leave ')], default='cash', string="Type")

    duration_type = fields.Selection([('hours', 'Hour'), ('days', 'Days')], string="Duration Type", default="hours",
                                     required=True)
    overtime_type = fields.Selection([('ph', 'Public Holiday'), ('working', 'Working Days'), ('weekend', 'Weekend')],
                                     string="Overtime Type", default="working", required=True)

    leave_type = fields.Many2one('hr.leave.type', string='Leave Type', domain="[('id', 'in', leave_compute)]")
    leave_compute = fields.Many2many('hr.leave.type', compute="_get_leave_type")
    rule_line_ids = fields.One2many('overtime.type.rule', 'type_line_id')
    coefficient = fields.Float("Coefficient", default='1.0',
                               help="Coefficient is to calculate with day/hour rate. "
                                    "Ex: OT Rate = Coefficient * Rate_Per_hour")

    @api.onchange('duration_type')
    def _get_leave_type(self):
        dur = ''
        ids = []
        if self.duration_type:
            if self.duration_type == 'days':
                dur = 'day'
            else:
                dur = 'hour'
            leave_type = self.env['hr.leave.type'].search([('request_unit', '=', dur)])
            for recd in leave_type:
                ids.append(recd.id)
            self.leave_compute = ids


class HrOverTimeTypeRule(models.Model):
    _name = 'overtime.type.rule'
    _description = "HR Overtime Type Rule"

    type_line_id = fields.Many2one('overtime.type', string='Over Time Type')
    duration_type = fields.Selection([('hours', 'Hour'), ('days', 'Days')], string="Duration Type", related='type_line_id.duration_type', readonly=True)
    name = fields.Char('Name', required=True)
    from_hrs = fields.Float('From', required=True)
    to_hrs = fields.Float('To', required=True)
    hrs_amount = fields.Float('Total Duration', required=True)
