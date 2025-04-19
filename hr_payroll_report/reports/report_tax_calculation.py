from datetime import time, datetime
from pytz import timezone
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ReportTaxCalculation(models.AbstractModel):
    # _name = 'report.module_name.report_name_qweb_template'
    _name = "report.hr_payroll_report.report_tax_calculation_template"
    _description = "Printing Tax Calculation"

    def _get_tax_calculation(self, date_from, date_to, company_id):
        payslip_obj = self.env['hr.payslip']
        payslips = payslip_obj.search([('state', 'in', ('draft,done')), ('date_from', '>=', date_from),
                                       ('date_to', '<=', date_to), ('company_id', '=', company_id[0])])
        print("=============payslips==============", payslips)

        if not payslips:
            raise ValidationError("There is no DONE Payslip(s) found in this period, please select new range or paylips records")
        # for payslip in payslips:

        return payslips

    @api.model
    def _get_report_values(self, docids, data):
        active_model = self.env.context.get("active_model")
        if data is None:
            data = {}
        if not docids:
            docids = data["form"].get("docids")
        folio_profile = self.env["hr.payslip"].browse(docids)
        date_from = data['form']['date_from']
        date_to = data['form']['date_to']
        company_id = data['form']['company_id']

        rm_act = self.with_context(data["form"].get("used_context", {}))
        _get_tax_calculation = rm_act._get_tax_calculation(
            date_from, date_to, company_id
        )

        return {
            "doc_ids": docids,
            "doc_model": active_model,
            "data": data["form"],
            "docs": folio_profile,
            "time": time,
            "get_tax_calculation": _get_tax_calculation,
        }