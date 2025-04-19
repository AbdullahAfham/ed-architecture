
from odoo import fields, models, _
from datetime import date, datetime, time
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError
import xlsxwriter
import base64


class PayrollReport(models.TransientModel):
    _name = "print.payroll.report.wizard"
    _description = "Print Payroll Report Wizard"

    date_from = fields.Date(string='Date From', required=True, help="End date",
        default=lambda self: fields.Date.to_string((datetime.now().replace(day=1))))
    date_to = fields.Date(string='Date To', required=True, help="End date", 
        default=lambda self: fields.Date.to_string((datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()))
    company_id = fields.Many2one('res.company', string='Company', required=True, index=True, 
        default=lambda self: self.env.company
    )
    # struct_id = fields.Many2one('hr.payroll.structure', string="Structure")
    # bank = fields.Selection([('aba', 'ABA Bank'), ('acleda', 'Acleda Bank'), ('chipmong', 'Chip Mong Bank')], default='aba')
    state = fields.Selection([('choose', 'choose'), ('get', 'get')], default='choose')
    name = fields.Char(string='File Name', readonly=True)
    data = fields.Binary(string='File', readonly=True)

    def check_date_range(self):
        if self.date_to < self.date_from:
            raise ValidationError(_('End Date should be greater than Start Date.'))

    def go_back(self):
        self.state = 'choose'
        return {
            'name': 'Payroll Report',
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new'
        }

    def get_payroll_report_list(self):
        payroll_report_list = []
        dic = {}
        seq = 0
        payslip_ids = self.env['hr.payslip'].search([('date_from', '>=', self.date_from),
                                                            ('date_to', '<=', self.date_to),
                                                            # ('state', 'in', ['done','paid']),
                                                            ])
        for slip in payslip_ids:
            # dic = {}
            data = {}
            id = slip.employee_id.registration_number
            ot_hour = 0.0
            ot_amount = 0.0
            absent = 0.0
            deduction = 0.0
            addition = 0.0
            adjustment = 0.0
            tool_lost = 0.0
            gross = 0.0
            first_payroll = 0.0
            advanced_hq = 0.0
            net = 0.0
            net_hq = 0.0
            tos = 0.0
            remain = 0.0
            for line in slip.line_ids:
                if line.code == 'OVERTIME':
                    ot_amount = line.total
                if line.code == 'ABSENT':
                    absent = line.total
                if line.code == 'DEDUCTIION':
                    deduction = line.total
                if line.code == 'ADDITION':
                    addition = line.total
                if line.code == 'ADJ':
                    adjustment = line.total
                if line.code == 'LOST':
                    tool_lost = line.total
                if line.code == 'FNET':
                    first_payroll = line.total
                if line.code == 'NET':
                    net = line.total
                if line.code == 'TOS':
                    tos = line.total

            data = {
                'no': seq + 1,
                'id': id,
                'name': slip.employee_id.name,
                'wage': slip.contract_id.wage,
                'ot_hour': ot_hour,
                'ot_amount': ot_amount,
                'absent': absent,
                'deduction': deduction,
                'addition': addition,
                'adjustment': adjustment,
                'tool_lost': tool_lost,
                'gross': gross,
                'first_payroll': first_payroll,
                'advanced_hq': advanced_hq,
                'net': net,
                'net_hq': net_hq,
                'tos': tos,
                'remain': remain,
            }
            seq = seq + 1

            if dic:
                if id in dic:
                    dic[id]['ot_hour'] += ot_hour
                    dic[id]['absent'] += absent
                    dic[id]['deduction'] += deduction
                    dic[id]['addition'] += addition
                    dic[id]['adjustment'] += adjustment
                    dic[id]['tool_lost'] += tool_lost
                    dic[id]['gross'] += gross
                    dic[id]['first_payroll'] += first_payroll
                    dic[id]['advanced_hq'] += advanced_hq
                    dic[id]['net'] += net
                    dic[id]['net_hq'] += net_hq
                    dic[id]['tos'] += tos
                    dic[id]['remain'] += remain
                else:
                    dic.update({id: data})
            if not dic:
                dic.update({id: data})

            # if not dic:
            #     dic.update({id: data})
            # else:
            #     for rec in payroll_report_list:
            #         if rec['id'] == slip.employee_id.registration_number:
            #             rec['ot_hour'] += ot_hour
            #             rec['absent'] += absent
            #             rec['deduction'] += deduction
            #             rec['addition'] += addition
            #             rec['adjustment'] += adjustment
            #             rec['tool_lost'] += tool_lost
            #             rec['gross'] += gross
            #             rec['first_payroll'] += first_payroll
            #             rec['advanced_hq'] += advanced_hq
            #             rec['net'] += net
            #             rec['net_hq'] += net_hq
            #             rec['tos'] += tos
            #             rec['remain'] += remain
            #         else:
            #             payroll_report_list.append(data)

        # print("==========payroll_report_list============", dic)

        return dic

    def print_xls_payroll_report(self):
        self.check_date_range()
        xls_filename = 'payroll_report.xlsx'
        workbook = xlsxwriter.Workbook('/tmp/' + xls_filename)
        worksheet = workbook.add_worksheet("Payroll Report")
        lists = self.get_payroll_report_list()

        # Format
        header_merge_format = workbook.add_format(
            {'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 10,
             'bg_color': '#D3D3D3', 'border': 1})
        header_data_format = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'font_size': 10, 'border': 1})

        # Initial value
        rows = 2

        # ------------------------------ Main Table Header --------------------------------

        worksheet.write(1, 0, "No", header_merge_format)
        worksheet.write(1, 1, "EMPL.ID", header_merge_format)
        worksheet.write(1, 2, "EMPLOYEE NAME", header_merge_format)
        worksheet.write(1, 3, "SALARY", header_merge_format)
        worksheet.write(1, 4, "OT AMOUNT", header_merge_format)
        worksheet.write(1, 5, "ABSENT", header_merge_format)
        worksheet.write(1, 6, "DEDUCTION", header_merge_format)
        worksheet.write(1, 7, "ADJUSTMENT", header_merge_format)
        worksheet.write(1, 8, "TOOL LOST", header_merge_format)
        worksheet.write(1, 9, "G_SALARY", header_merge_format)
        worksheet.write(1, 10, "Advanced - TA", header_merge_format)
        worksheet.write(1, 11, "B-IN-I-TA", header_merge_format)
        worksheet.write(1, 12, "TOS", header_merge_format)
        worksheet.write(1, 13, "ADDITION", header_merge_format)
        worksheet.write(1, 14, "NET PAY", header_merge_format)

        for line in lists:
            # --------------------------------- Display Total --------------------------------
            worksheet.write(rows, 0, lists[line]['no'], header_data_format)
            worksheet.write(rows, 1, lists[line]['id'], header_data_format)
            worksheet.write(rows, 2, lists[line]['name'], header_data_format)
            worksheet.write(rows, 3, lists[line]['wage'], header_data_format)
            worksheet.write(rows, 4, lists[line]['ot_amount'], header_data_format)
            worksheet.write(rows, 5, lists[line]['absent'], header_data_format)
            worksheet.write(rows, 6, lists[line]['deduction'], header_data_format)
            worksheet.write(rows, 7, lists[line]['adjustment'], header_data_format)
            worksheet.write(rows, 8, lists[line]['tool_lost'], header_data_format)
            worksheet.write(rows, 9, lists[line]['gross'], header_data_format)
            worksheet.write(rows, 10, lists[line]['first_payroll'], header_data_format)
            worksheet.write(rows, 11, lists[line]['net'], header_data_format)
            worksheet.write(rows, 12, lists[line]['tos'], header_data_format)
            worksheet.write(rows, 13, lists[line]['addition'], header_data_format)
            worksheet.write(rows, 14, lists[line]['remain'], header_data_format)
            # --------------------------------------------------------------------------------
            rows += 1

        workbook.close()
        self.write({
            'state': 'get',
            'data': base64.b64encode(open('/tmp/' + xls_filename, 'rb').read()),
            'name': xls_filename
        })
        return {
            'name': 'Payroll Report',
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new'
        }
