from odoo import _, _lt, api, fields, models
from datetime import date, datetime, time


class HrPayroll(models.Model):
    _inherit = 'hr.payslip'

    khr_currency_id = fields.Many2one('res.currency', string='Khmer Riel', required=True, tracking=True, 
        related='payslip_run_id.khr_currency_id',
        default=lambda self: self.env['res.currency'].search([('name', '=', 'KHR')])
    )
    exchange_date = fields.Date('Exchange Date', required=True,
        related='payslip_run_id.exchange_date',
        default=lambda self: fields.Date.to_string(date.today())
    )
    exchange_rate = fields.Float('Exchange Rate', required=True, store=True, 
        related='payslip_run_id.exchange_rate',
        default=lambda self: self.khr_currency_id.rate
    )
    payroll_type = fields.Selection(
        related='payslip_run_id.payroll_type'
    )
    first_paid = fields.Float(
        string="First Paid"
    )
    first_payroll = fields.Boolean(
        string="First Payroll"
    )

    @api.onchange('exchange_date')
    def onchange_exchange_date(self):
        if self.payslip_run_id:
            self.exchange_date = self.payslip_run_id.exchange_date
        # print("======================payslip_run_id======================", self.payslip_run_id.exchange_date)
        rate_id = self.env['res.currency.rate'].search([('currency_id', '=', self.khr_currency_id.id),
                                                        ('name', '=', self.exchange_date)], limit=1)
        if rate_id:
            self.exchange_rate = rate_id.rate

    def compute_sheet(self):
        for sl in self:
            if sl.payroll_type == 'second':
                fnet = 0.0
                payslips = self.env['hr.payslip'].search([('employee_id', '=', sl.employee_id.id),
                                                          ('date_from', '>=', sl.date_from),
                                                          ('date_to', '<=', sl.date_to),
                                                          ('state', 'in', ['done', 'paid']),
                                                          ])
                for s in payslips:
                    for l in s.line_ids:
                        if l.code == 'FNET':
                            fnet = l.total
                if fnet != 0.0:
                    sl.first_paid = fnet
                    sl.first_payroll = True
        return super().compute_sheet()

