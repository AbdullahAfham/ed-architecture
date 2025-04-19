from odoo import fields, models
# import time
from datetime import datetime, date, time
from pytz import timezone

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class ReportPayrollInfo(models.AbstractModel):
    # _name = 'report.module_name.report_name_qweb_template'
    _name = "report.hr_payroll_report.report_payroll_information_template"
    _description = "Printing Information for Payrolling"

    def _get_payroll_info(self, date_from, date_to, company_id):
        payslip_obj = self.env['hr.payslip']
        contract_obj = self.env['hr.contract']
        print("===", company_id[0])
        contracts = contract_obj.search([('state', '=', 'open'), ('company_id', '=', company_id[0])])
        for contract in contracts:
            date_f = fields.Datetime.now().strptime(date_from, "%Y-%m-%d")
            date_t = fields.Datetime.now().strptime(date_to, "%Y-%m-%d")
            overtime_ids = self.env['hr.overtime'].search([('employee_id', '=', contract.employee_id.id),
                                                          ('contract_id', '=', contract.id),
                                                          ('state', '=', 'approved'),
                                                          ('payslip_paid', '=', False),
                                                          ('date_from', '>=', date_f),
                                                          ('date_to', '<=', date_t)])
            ot_ph = 0.0
            ot_working = 0.0
            ot_weekend = 0.0
            for overtime_id in overtime_ids:
                if overtime_id.duration_type == 'hours':
                    d = overtime_id.days_no_tmp/8
                else:
                    d = overtime_id.days_no_tmp
                if overtime_id.overtime_type_id.overtime_type == 'ph':
                    ot_ph = ot_ph + d
                elif overtime_id.overtime_type_id.overtime_type == 'working':
                    ot_working = ot_working + d
                else:
                    ot_weekend = ot_weekend + d
            contract.ot_ph = round(ot_ph, 2)
            contract.ot_working_day = round(ot_working, 2)
            contract.ot_weekend = round(ot_weekend, 2)
            calendar = contract.resource_calendar_id
            tz = timezone(calendar.tz)
            leaves = {}
            unpaid = 0.0
            leave_data = contract.employee_id.list_leaves(date_f, date_t,
                                             calendar=contract.resource_calendar_id)

            for day, hours, leave in leave_data:
                holiday = leave.holiday_id
                current_leave_struct = leaves.setdefault(holiday.holiday_status_id.id, {
                    'name': holiday.holiday_status_id.name or _('Global Leaves'),
                    'sequence': 5,
                    'code': holiday.holiday_status_id.code or 'GLOBAL',
                    'number_of_days': 0.0,
                    'number_of_hours': 0.0,
                    'contract_id': contract.id,
                })
                current_leave_struct['number_of_hours'] += hours
                work_hours = calendar.get_work_hours_count(
                    tz.localize(datetime.combine(day, time.min)),
                    tz.localize(datetime.combine(day, time.max)),
                    compute_leaves=False,
                )
                if work_hours:
                    current_leave_struct['number_of_days'] += hours / work_hours
            print("=================leaves==========", contract.employee_id.name, leaves)
            for leav in leaves:
                if leaves[leav]['code'] == 'UNPAID':
                    contract.unpaid_num = leaves[leav]['number_of_days']
        return contracts

    @api.model
    def _get_report_values(self, docids, data):
        print("=============_get_report_values================", data['form']['company_id'])
        active_model = self.env.context.get("active_model")
        if data is None:
            data = {}
        if not docids:
            docids = data["form"].get("docids")
        folio_profile = self.env["hr.contract"].browse(docids)
        date_from = data['form']['date_from']
        date_to = data['form']['date_to']
        company_id = data['form']['company_id']

        rm_act = self.with_context(data["form"].get("used_context", {}))
        _get_payroll_info = rm_act._get_payroll_info(
            date_from, date_to, company_id
        )
        print("=================_get_payroll_info=================", _get_payroll_info)
        return {
            "doc_ids": docids,
            "doc_model": active_model,
            "data": data["form"],
            "docs": folio_profile,
            "time": time,
            "get_payroll_info": _get_payroll_info,
        }