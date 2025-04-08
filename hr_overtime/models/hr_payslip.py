import logging

from odoo import models, api, fields, _
from datetime import datetime
from odoo.tools.profiler import Profiler, PeriodicCollector


# class HrPayslipWorkdays(models.Model):
#     _inherit = 'hr.payslip.worked_days'

#     overtime_ids = fields.Many2many('hr.overtime')


class PayslipOverTime(models.Model):
    _inherit = 'hr.payslip'

    overtime_ids = fields.One2many('hr.overtime', 'payslip_id', string='Overtime', readonly=False,
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]})
    overtimes_count = fields.Integer(compute='_compute_overtimes_count')

    @api.depends('overtime_ids', 'overtime_ids.payslip_id')
    def _compute_overtimes_count(self):
        for payslip in self:
            payslip.overtimes_count = len(payslip.overtime_ids)

    def compute_sheet(self):
        with Profiler(collectors=['sql', PeriodicCollector(interval=0.1)]):
            payslips = self.filtered(lambda slip: slip.state in ['draft', 'verify'])
            payslips.overtime_ids = False

            for slip in payslips:
                overtimes = self.env['hr.overtime'].search([
                    ('employee_id', '=', slip.employee_id.id),
                    ('state', '=', 'approved'),
                    ('date_from', '>=', slip.date_from.strftime('%Y-%m-%d')),
                    ('date_to', '<=', slip.date_to.strftime('%Y-%m-%d')),
                    # ('payslip_id', '=', False),
                ])

                # payslip_overtimes = overtimes.filtered(lambda s: s.employee_id == slip.employee_id)
                slip.overtime_ids = [(5, 0, 0)] + [(4, s.id, False) for s in overtimes]

            return super().compute_sheet()

    @api.model_create_multi
    def create(self, vals_list):
        payslips = super().create(vals_list)
        draft_slips = payslips.filtered(lambda p: p.employee_id and p.state == 'draft')
        payslips.overtime_ids = False

        if not draft_slips:
            return payslips

        for slip in draft_slips:
            overtimes = self.env['hr.overtime'].search([
                ('employee_id', '=', slip.employee_id.id),
                ('state', '=', 'approved'),
                ('date_from', '>=', slip.date_from.strftime('%Y-%m-%d')),
                ('date_to', '<=', slip.date_to.strftime('%Y-%m-%d')),
            ])
            
            # payslip_overtimes = overtimes.filtered(lambda s: s.employee_id == slip.employee_id)
            slip.overtime_ids = [(5, 0, 0)] + [(4, s.id, False) for s in overtimes]
        return payslips

    def write(self, vals):
        res = super().write(vals)
        if 'overtime_ids' in vals:
            self._compute_overtime_input_line_ids()
        if 'input_line_ids' in vals:
            self._update_overtime_sheets()
        return res

    def _compute_overtime_input_line_ids(self):
        logging.info('compute overtime input line ids')
        overtime_type = self.env.ref('hr_overtime.overtime_other_input', raise_if_not_found=False)
        for payslip in self:
            total = sum(payslip.overtime_ids.mapped('cash_hrs_amount')) + sum(payslip.overtime_ids.mapped('cash_day_amount'))
            logging.info('total: %s', total)
            logging.info('overtime_type: %s', overtime_type)
            if not total or not overtime_type:
                continue
            lines_to_remove = payslip.input_line_ids.filtered(lambda x: x.input_type_id == overtime_type)
            input_lines_vals = [(2, line.id, False) for line in lines_to_remove]
            input_lines_vals.append((0, 0, {
                'name': '\n'.join([desc for desc in payslip.overtime_ids.mapped('desc') if desc]),
                'amount': total,
                'input_type_id': overtime_type.id
            }))
            payslip.update({'input_line_ids': input_lines_vals})

    def _update_overtime_sheets(self):
        overtime_type = self.env.ref('hr_overtime.overtime_other_input', raise_if_not_found=False)
        for payslip in self:
            if not payslip.input_line_ids.filtered(lambda line: line.input_type_id == overtime_type):
                payslip.overtime_ids.write({'payslip_id': False})

    def action_payslip_cancel(self):
        res = super(PayslipOverTime, self).action_payslip_cancel()
        self.write({'overtime_ids': False})
        return res

    def action_payslip_done(self):
        res = super(PayslipOverTime, self).action_payslip_done()
        for overtime_id in self.overtime_ids:
            overtime_id.set_to_paid()
        return res

    def open_overtimes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Overtimes'),
            'res_model': 'hr.overtime',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.overtime_ids.ids)],
        }
