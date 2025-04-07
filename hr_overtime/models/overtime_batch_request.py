# -*- coding: utf-8 -*-
import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from dateutil import relativedelta
import pytz
from datetime import datetime, timedelta

class HrBatchOverTime(models.Model):
    _name = 'hr.batch.overtime'
    _description = "HR Batch Overtime"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    employee_id = fields.Many2one('hr.employee')
    name = fields.Char('Reference', readonly=True)
    overtime_ids = fields.One2many('hr.overtime', 'batch_id', string="Employees")
    date = fields.Date('Date', compute="_get_date")
    date_from = fields.Datetime('Date From')
    date_to = fields.Datetime('Date to')
    break_hours = fields.Float('Break Time')
    days_no_tmp = fields.Float('Total Hours', compute="_get_days", store=True)
    total_days_no_tmp = fields.Float('Total Duration', compute="_get_total_days", store=True)
    days_no = fields.Float('No. of Days', store=True)
    desc = fields.Text('Description')

    cancel_reason = fields.Text('Refuse Reason')
    leave_id = fields.Many2one('hr.leave.allocation',
                               string="Leave ID")
    attchd_copy = fields.Binary('Attach A File')
    attchd_copy_name = fields.Char('File Name')
    type = fields.Selection([
        ('cash', 'Cash')
        # , ('leave', 'leave')
    ], default="cash", required=True, string="Type")
    overtime_type_id = fields.Many2one('overtime.type',
                                       domain="[('type','=', type ), ('duration_type','=', duration_type)]")
    public_holiday = fields.Char(string='Public Holiday', readonly=True)
    attendance_ids = fields.Many2many('hr.attendance', string='Attendance')
    duration_type = fields.Selection([('hours', 'Hour'), ('days', 'Days')], string="Duration Type", default="hours",
                                     required=True)
    cash_hrs_amount = fields.Float(string='Overtime Amount', compute="_compute_cash_hrs_amount", readonly=True)
    cash_day_amount = fields.Float(string='Overtime Amount', readonly=True)
    payslip_paid = fields.Boolean('Paid in Payslip', readonly=True)
    creator_id = fields.Many2one('res.users', string='Requester', readonly=True, tracking=True)
    creator_list = fields.Many2many('res.users', string='Requesters', copy=False)
    approver_id = fields.Many2one('res.users', string='Manager', required=True, tracking=True)
    hr_officer_approver_id = fields.Many2one('res.users', string='HR Manager', required=True,
                                             tracking=True)
    om_approver_id = fields.Many2one('res.users', string='Operation Manager',
                                     tracking=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True, copy=False, help="Company",
                                 default=lambda self: self.env['res.company']._company_default_get(),
                                 states={'draft': [('readonly', False)]})
    manager_id = fields.Many2one('res.users', string="Manager", store=True)
    user_id = fields.Many2one('res.users', string="User", default=lambda self: self.env.uid, store=True)
    current_user_boolean = fields.Boolean()
    project_id = fields.Many2one('project.project', string="Project")
    state = fields.Selection([('draft', 'Draft'),
                              ('approval', 'Waiting'),
                              ('pm_approval', 'PM Approved'),
                              ('hr_approval', 'HR Validated'),
                              ('approved', 'OM Approved'),
                              ('cancel', 'Cancelled'),
                              ('refused', 'Refused')],
                             string="State", tracking=True, default="draft")

    can_pm_approve = fields.Boolean(compute='_compute_can_approve')
    can_hr_approve = fields.Boolean(compute='_compute_can_approve')
    can_om_approve = fields.Boolean(compute='_compute_can_approve')
    can_refuse = fields.Boolean(compute='_compute_can_refuse')
    can_reset_to_draft = fields.Boolean(compute='_compute_can_reset')
    can_reset_to_waiting = fields.Boolean(compute='_compute_can_reset')
    can_reset_to_pm_approval = fields.Boolean(compute='_compute_can_reset')
    can_reset_to_hr_approval = fields.Boolean(compute='_compute_can_reset')

    @api.depends('date_from')
    def _get_date(self):
        for rec in self:
            if rec.date_from:
                converted_date = rec.date_from.astimezone(pytz.timezone(self.env.user.tz)) \
                    if self.env.user.tz else rec.date_from
                rec.date = converted_date.date()
            else:
                rec.date = False

    def _compute_can_approve(self):
        for rec in self:
            rec.can_pm_approve = self.env.user == rec.approver_id and rec.state == 'approval'
            rec.can_hr_approve = self.env.user == rec.hr_officer_approver_id and rec.state == 'pm_approval'
            rec.can_om_approve = self.env.user == rec.om_approver_id and rec.state == 'hr_approval'

    def _compute_can_reset(self):
        for rec in self:
            rec.can_reset_to_draft = self.env.user == rec.user_id and rec.state in ['approval', 'refused', 'cancel']
            rec.can_reset_to_waiting = self.env.user == rec.approver_id and rec.state == 'pm_approval'
            rec.can_reset_to_pm_approval = self.env.user == rec.hr_officer_approver_id and rec.state == 'hr_approval'
            rec.can_reset_to_hr_approval = self.env.user == rec.om_approver_id and rec.state == 'approved'

    def _compute_can_refuse(self):
        for rec in self:
            if rec.state == 'approval':
                rec.can_refuse = self.env.user == rec.approver_id
            elif rec.state == 'pm_approval':
                rec.can_refuse = self.env.user == rec.hr_officer_approver_id
            elif rec.state == 'hr_approval':
                rec.can_refuse = self.env.user == rec.om_approver_id
            else:
                rec.can_refuse = False

    @api.onchange('project_id')
    def _onchange_project_id(self):
        for rec in self:
            if rec.project_id:
                rec.approver_id = rec.project_id.user_id.id
                rec.om_approver_id = rec.project_id.om_id.id

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

        # for overtime_batch in self:
        #     for overtime_id in overtime_batch.overtime_ids:
        #         overtime_id._get_days()
        #     overtime_batch.days_no_tmp = sum(overtime_batch.overtime_ids.mapped('days_no_tmp'))

    @api.depends('overtime_ids', 'duration_type', 'date_from', 'date_to', 'break_hours')
    def _get_total_days(self):
        for overtime_batch in self:
            overtime_batch.total_days_no_tmp = sum(overtime_batch.overtime_ids.mapped('days_no_tmp'))

    @api.onchange('overtime_type_id')
    @api.depends('type', 'overtime_ids')
    def _compute_cash_hrs_amount(self):
        for overtime_batch in self:
            for overtime_id in overtime_batch.overtime_ids:
                overtime_id._get_hour_amount()
            overtime_batch.cash_hrs_amount = sum(overtime_batch.overtime_ids.mapped('cash_hrs_amount'))
            overtime_batch.payslip_paid = all(overtime_batch.overtime_ids.mapped('payslip_paid'))

    def activity_update(self):
        to_clean, to_do = self.env['hr.batch.overtime'], self.env['hr.batch.overtime']
        for overtime_batch in self:
            # start = UTC.localize(holiday.date_from).astimezone(timezone(holiday.employee_id.tz or 'UTC'))
            # end = UTC.localize(holiday.date_to).astimezone(timezone(holiday.employee_id.tz or 'UTC'))
            note = _(
                'You have a Batch Overtime Request to Approve from %(name)s',
                name=overtime_batch.user_id.name
            )
            if overtime_batch.state == 'draft':
                to_clean |= overtime_batch
            elif overtime_batch.state == 'approval':
                overtime_batch.activity_schedule(
                    'hr_overtime.mail_act_hr_overtime_pm',
                    note=note,
                    user_id=overtime_batch.sudo().approver_id.id or self.env.user.id)
            elif overtime_batch.state == 'pm_approval':
                overtime_batch.activity_feedback(['hr_overtime.mail_act_hr_overtime_pm'])
                overtime_batch.activity_schedule(
                    'hr_overtime.mail_act_hr_overtime_hr_officer',
                    note=note,
                    user_id=overtime_batch.sudo().hr_officer_approver_id.id or self.env.user.id)
            elif overtime_batch.state == 'hr_approval':
                overtime_batch.activity_feedback(['hr_overtime.mail_act_hr_overtime_hr_officer'])
                overtime_batch.activity_schedule(
                    'hr_overtime.mail_act_hr_overtime_om',
                    note=note,
                    user_id=overtime_batch.sudo().om_approver_id.id or self.env.user.id)
            elif overtime_batch.state == 'approved':
                to_do |= overtime_batch
            elif overtime_batch.state == 'refused':
                to_clean |= overtime_batch
        if to_clean:
            to_clean.activity_unlink([
                'hr_overtime.mail_act_hr_overtime_pm',
                'hr_overtime.mail_act_hr_overtime_hr_officer',
                'hr_overtime.mail_act_hr_overtime_om',
            ])
        if to_do:
            to_do.activity_feedback([
                'hr_overtime.mail_act_hr_overtime_pm',
                'hr_overtime.mail_act_hr_overtime_hr_officer',
                'hr_overtime.mail_act_hr_overtime_om',
            ])

    def submit_request(self):
        if len(self.overtime_ids) > 0:
            self.sudo().overtime_ids.submit_request()
        else:
            raise ValidationError(_("You can't submit empty batch overtime request"))

        # notification to employee :
        recipient_partners = [(4, self.user_id.partner_id.id)]
        body = "Your OT Request Has been Submitted ..."
        msg = _(body)
        self.message_post(body=msg)

        self.sudo().write({
            'state': 'approval',
        })
        # update activity
        self.activity_update()
        return True

    def pm_approve(self):
        for overtime_batch in self:
            if overtime_batch.state == 'approval':
                if len(overtime_batch.overtime_ids) > 0:
                    overtime_batch.sudo().overtime_ids.approve()

                overtime_batch.sudo().write({
                    'state': 'pm_approval',
                })
                # update activity
                overtime_batch.activity_update()

    def hr_office_approve(self):
        for overtime_batch in self:
            if overtime_batch.state == 'pm_approval':
                if not overtime_batch.overtime_type_id:
                    raise ValidationError(_("Please Select Overtime Type in Batch Overtime Request "
                                            + overtime_batch.name))

                if len(overtime_batch.overtime_ids) > 0:
                    overtime_batch.sudo().overtime_ids.submit_to_finance()

                overtime_batch.sudo().write({
                    'state': 'hr_approval',
                })
                # update activity
                overtime_batch.activity_update()

    def om_approve(self):
        for overtime_batch in self:
            if overtime_batch.state == 'hr_approval':
                if len(overtime_batch.overtime_ids) > 0:
                    overtime_batch.sudo().overtime_ids.finance_approve()

                overtime_batch.sudo().write({
                    'state': 'approved',
                })
                # update activity
                overtime_batch.activity_update()

    def approve_all(self):
        # check if all overtime request are in the same state
        if len(self) > 0:
            if len(set(self.mapped('state'))) > 1:
                raise ValidationError(_("You can't approve overtime request in different states"))

        # get state
        state = self.mapped('state')[0]

        # check if the user is allowed to approve overtime request
        if state == 'approval':
            # check if all overtime request cm_sm_approve is the current user
            if len(self.filtered(lambda overtime_batch: overtime_batch.approver_id != self.env.user)) > 0:
                raise ValidationError(_("You can't approve overtime request that are not assigned to you"))
            self.pm_approve()
        elif state == 'pm_approval':
            # check if all overtime request om_approve is the current user
            if len(self.filtered(lambda overtime_batch: overtime_batch.hr_officer_approver_id != self.env.user)) > 0:
                raise ValidationError(_("You can't approve overtime request that are not assigned to you"))
            self.hr_office_approve()
        elif state == 'hr_approval':
            # check if all overtime request pm_approve is the current user
            if len(self.filtered(lambda overtime_batch: overtime_batch.om_approver_id != self.env.user)) > 0:
                raise ValidationError(_("You can't approve overtime request that are not assigned to you"))
            self.om_approve()
        else:
            raise ValidationError(_("You can't approve overtime request in " + state + " state"))

    def cancel(self):
        if len(self.overtime_ids) > 0:
            self.sudo().overtime_ids.reject()

        self.sudo().write({
            'state': 'cancel',
        })
        # update activity
        self.activity_update()
        return True

    def reject(self):
        if len(self.overtime_ids) > 0:
            self.sudo().overtime_ids.reject()

        self.sudo().write({
            'state': 'refused',
        })
        # update activity
        self.activity_update()
        return True

    def action_draft(self):
        if len(self.overtime_ids) > 0:
            self.sudo().overtime_ids.action_draft()
        self.activity_unlink([
            'hr_overtime.mail_act_hr_overtime_pm',
            'hr_overtime.mail_act_hr_overtime_hr_officer',
            'hr_overtime.mail_act_hr_overtime_om',
        ])
        return self.sudo().write({
            'state': 'draft',
            'overtime_type_id': False,
        })

    def action_reset_to_waiting(self):
        for overtime_batch in self:
            # check if the state is pm_approval and the user is the approver_id
            if overtime_batch.state == 'pm_approval' and overtime_batch.approver_id == self.env.user:
                # reset overtime request to approval state
                overtime_batch.sudo().overtime_ids.action_reset_to_approval()

                overtime_batch.sudo().write({
                    'state': 'approval',
                })
                # unlink mail_act_hr_overtime_hr_officer activity
                overtime_batch.activity_unlink(['hr_overtime.mail_act_hr_overtime_hr_officer'])
            else:
                raise ValidationError(_("You can't reset overtime request in " + overtime_batch.state + " state"))

    def action_reset_to_pm_approval(self):
        for overtime_batch in self:
            # check if the state is hr_approval and the user is the approver_id
            if overtime_batch.state == 'hr_approval' and overtime_batch.hr_officer_approver_id == self.env.user:
                # reset overtime request to officer_approval state
                overtime_batch.sudo().overtime_ids.action_reset_to_officer_approval()

                overtime_batch.sudo().write({
                    'state': 'pm_approval',
                })
                # unlink mail_act_hr_overtime_om activity
                overtime_batch.activity_unlink(['hr_overtime.mail_act_hr_overtime_om'])
            else:
                raise ValidationError(_("You can't reset overtime request in " + overtime_batch.state + " state"))

    def action_reset_to_hr_approval(self):
        for overtime_batch in self:
            # check if the state is approved and the user is the approver_id
            if overtime_batch.state == 'approved' and overtime_batch.om_approver_id == self.env.user:
                # reset overtime request to finance_approval state
                overtime_batch.sudo().overtime_ids.action_reset_to_finance_approval()

                overtime_batch.sudo().write({
                    'state': 'hr_approval',
                })
            else:
                raise ValidationError(_("You can't reset overtime request in " + overtime_batch.state + " state"))

    # override _message_auto_subscribe_followers method to add the approvers
    def _message_auto_subscribe_followers(self, updated_values, subtype_ids):
        res = super(HrBatchOverTime, self)._message_auto_subscribe_followers(updated_values, subtype_ids)
        for overtime_batch in self:
            if 'creator_id' in updated_values and updated_values['creator_id']:
                creator = overtime_batch.env['res.users'].browse(updated_values['creator_id'])
                res.append((creator.partner_id.id, subtype_ids, False))
            if 'approver_id' in updated_values:
                approver = overtime_batch.env['res.users'].browse(updated_values['approver_id'])
                res.append((approver.partner_id.id, subtype_ids, False))
            if 'hr_officer_approver_id' in updated_values:
                hr_officer_approver = overtime_batch.env['res.users'].browse(updated_values['hr_officer_approver_id'])
                res.append((hr_officer_approver.partner_id.id, subtype_ids, False))
            if 'om_approver_id' in updated_values:
                om_approver = overtime_batch.env['res.users'].browse(updated_values['om_approver_id'])
                res.append((om_approver.partner_id.id, subtype_ids, False))
        return res

    # action check overtime request to validate the overtime request with overtime attendance
    def action_check_overtime_request(self):
        for overtime_batch in self:
            for overtime in overtime_batch.overtime_ids:
                # get overtime attendance with the same employee_id, date_from and project_id
                overtime_attendances = overtime_batch.env['overtime.attendance'].search([
                    ('name', '=', overtime.employee_id.id),
                    ('overtime_id', '=', False),
                ])
                overtime_attendance = overtime_attendances.filtered(
                    lambda x: x.att_date == overtime_batch.date
                )
                if overtime_attendance:
                    # set overtime_id in overtime attendance
                    overtime_attendance.sudo().write({
                        'overtime_id': overtime.id,
                    })

                    # set scan_ot_in and scan_ot_out in overtime
                    overtime.sudo().write({
                        'scan_ot_in': overtime_attendance.ot_in,
                        'scan_ot_out': overtime_attendance.ot_out,
                    })

    @api.model
    def create(self, values):
        seq = self.env['ir.sequence'].next_by_code('hr.batch.overtime') or '/'
        values['name'] = seq

        record = super(HrBatchOverTime, self.sudo()).create(values)

        # update creator_id as create_uid
        if not record.creator_id:
            record.sudo().write({
                'creator_id': record.create_uid.id,
            })

        # add creator_id to creator_list field
        if record.creator_id:
            record.sudo().write({
                'creator_list': [(4, record.creator_id.id), (4, record.create_uid.id)],
            })
        else:
            record.sudo().write({
                'creator_list': [(4, record.create_uid.id)],
            })

        partner_ids_list = [
                record.approver_id.partner_id.id,
                record.hr_officer_approver_id.partner_id.id,
                record.om_approver_id.partner_id.id
            ]

        if record.creator_id:
            partner_ids_list.append(record.creator_id.partner_id.id)

        # add users to followers
        record.message_subscribe(partner_ids=partner_ids_list)
        return record

    def write(self, values):
        res = super(HrBatchOverTime, self).write(values)

        # if creator_id is changed, append the new creator_id to creator_list field
        if 'creator_id' in values:
            self.sudo().write({
                'creator_list': [(4, values['creator_id'])],
            })

        creator_list_partner_ids = [creator_id.partner_id.id for creator_id in self.creator_list]

        # new approver list
        new_approver_list = [
            self.creator_id.partner_id.id,
            self.approver_id.partner_id.id,
            self.hr_officer_approver_id.partner_id.id,
            self.om_approver_id.partner_id.id,
            self.user_id.partner_id.id
        ]

        # add creator partner id to new_approver_list if it is not in the list
        for creator_partner_id in creator_list_partner_ids:
            if creator_partner_id not in new_approver_list:
                new_approver_list.append(creator_partner_id)

        # unsubscribe followers if it is not in the approver list
        self.message_unsubscribe(partner_ids=[follower_id.partner_id.id for follower_id in self.message_follower_ids
                                              if follower_id.partner_id.id not in new_approver_list])

        return res

    def unlink(self):
        for batch in self:
            if batch.state not in ['draft', 'approval', 'pm_approval']:
                raise UserError(_('You cannot delete TIL request which is not in draft state.'))
            else:
                batch.overtime_ids.unlink()
        return super(HrBatchOverTime, self).unlink()

    def action_clean_batch_overtime(self):
        local_tz = pytz.timezone(self.env.user.partner_id.tz or 'GMT')
        bot_ids = self.env['hr.batch.overtime'].search([('state', '=', 'draft')])
        now = fields.datetime.now()
        for bot in bot_ids:
            t_date = local_tz.localize(now, is_dst=None)
            to_date = t_date + timedelta(hours=7)
            utc_dt = to_date.strftime("%Y-%m-%d %H:%M:%S")
            tod_date = datetime.strptime(utc_dt, "%Y-%m-%d %H:%M:%S")
            if bot.date_from:
                dfrom = now
            else:
                dfrom = now
            d_from = local_tz.localize(dfrom, is_dst=None)
            da_from = d_from + timedelta(hours=7)
            dat_from = da_from.strftime("%Y-%m-%d %H:%M:%S")
            date_from = datetime.strptime(dat_from, "%Y-%m-%d %H:%M:%S")

            late_tmp = date_from - tod_date
            if late_tmp.days > 0:
                bot.reject()
                continue
        return True
