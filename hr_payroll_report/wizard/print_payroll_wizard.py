
from odoo import fields, models
from datetime import date, datetime, time
from datetime import timedelta
from dateutil.relativedelta import relativedelta


class PrintPayrollWizard(models.TransientModel):
    _name = "print.payroll.wizard"
    _description = "Print Payroll Wizard"

    date_from = fields.Date(string='Date From', required=True, help="End date",
        default=lambda self: fields.Date.to_string((datetime.now().replace(day=1))))
    date_to = fields.Date(string='Date To', required=True, help="End date", 
        default=lambda self: fields.Date.to_string((datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()))
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env['res.company']._company_default_get())

    def report_print_payroll_info(self):

        data = {
            "ids": self.ids,
            "model": "hr.contract",
            "form": self.read(["date_from", "date_to", "company_id"])[0],
        }
        return self.env.ref(
            "hr_payroll_report.report_payroll_information_detail"
        ).report_action(self, data=data)


class PrintTaxWizard(models.TransientModel):
    _name = "print.tax.wizard"
    _description = "Print Tax Calculation Wizard"

    date_from = fields.Date(string='Date From', required=True, help="End date",
                            default=lambda self: fields.Date.to_string(
                                (datetime.now().replace(day=1))))
    date_to = fields.Date(string='Date To', required=True, help="Start date",
                          default=lambda self: fields.Date.to_string(
                              (datetime.now().replace(day=30))))
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env['res.company']._company_default_get())

    def report_print_tax_calculation(self):

        data = {
            "ids": self.ids,
            "model": "hr.payslip",
            "form": self.read(["date_from", "date_to", "company_id"])[0],
        }
        return self.env.ref(
            "hr_payroll_report.report_tax_calculation_detail"
        ).report_action(self, data=data)