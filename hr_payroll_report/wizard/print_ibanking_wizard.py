
from odoo import fields, models, _
from datetime import date, datetime, time
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError
import xlsxwriter
import base64


class PrintiBanking(models.TransientModel):
    _name = "print.ibanking.wizard"
    _description = "Print iBanking Wizard"

    date_from = fields.Date(string='Date From', required=True, help="End date",
        default=lambda self: fields.Date.to_string((datetime.now().replace(day=1))))
    date_to = fields.Date(string='Date To', required=True, help="End date", 
        default=lambda self: fields.Date.to_string((datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()))
    company_id = fields.Many2one('res.company', string='Company', required=True, index=True, 
        default=lambda self: self.env.company
    )
    struct_id = fields.Many2one('hr.payroll.structure', string="Structure")
    bank = fields.Selection([('vattanac', 'VATTANAC'),('aba', 'ABA Bank'), ('acleda', 'Acleda Bank'), ('chipmong', 'Chip Mong Bank')], default='aba')
    state = fields.Selection([('choose', 'choose'), ('get', 'get')], default='choose')
    name = fields.Char(string='File Name', readonly=True)
    data = fields.Binary(string='File', readonly=True)

    def check_date_range(self):
        if self.date_to < self.date_from:
            raise ValidationError(_('End Date should be greater than Start Date.'))

    def go_back(self):
        self.state = 'choose'
        return {
            'name': 'iBanking Report',
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new'
        }

    def get_ibanking_list(self):
        ibanking_list = []
        seq = 0
        payslip_lines = self.env['hr.payslip.line'].search([('code', '=', 'NET'),
                                                            ('slip_id.struct_id', '=', self.struct_id.id),
                                                            ('slip_id.date_from', '>=', self.date_from),
                                                            ('slip_id.date_to', '<=', self.date_to),
                                                            # ('slip_id.state', '=', 'done')
                                                            ])
        for line in payslip_lines:
            data = {}
            if self.bank == 'aba':
                data = {
                    'name': line.employee_id.name,
                    'id': seq + 1,
                    'bank_number': line.employee_id.bank_account_id.acc_number,
                    'amount': line.amount,
                }
                seq = seq +1
            if self.bank == 'acleda':
                data = {
                    'no': seq + 1,
                    'bank_number': line.employee_id.bank_account_id.acc_number,
                    'name': line.employee_id.name,
                    'currency': 'USD',
                    'amount': line.amount,
                    'date': self.date_to,
                    'narrative': 'Payroll',
                }
                seq = seq + 1
            if self.bank == 'chipmong':
                data = {
                    'no': seq + 1,
                    'bank_number': line.employee_id.bank_account_id.acc_number,
                    'name': line.employee_id.name,
                    'currency': 'USD',
                    'amount': line.amount,
                    'date': self.date_to,
                    'narrative': 'Payroll',
                }
                seq = seq + 1
            if self.bank == line.slip_id.bank == 'vattanac':
                data = {
                    'no': seq + 1,
                    # 'bank_number': line.employee_id.bank_account_id.acc_number,
                    'bank_number': line.employee_id.bank_account_num,
                    'bank_name': line.employee_id.bank_account_holder_name,
                    'address': line.employee_id.address_home_id.street,
                    # 'bic': 'BREDKHP2',
                    'amount': line.amount,
                    'currency': 'USD',
                    'narrative': line.slip_id.number,
                    'date': self.date_to,
                }
                seq = seq + 1
            ibanking_list.append(data)
        print("==========ibanking_list============", ibanking_list)

        return ibanking_list

    def print_xls_ibanking_report(self):
        self.check_date_range()
        xls_filename = 'ibanking_report.xlsx'
        workbook = xlsxwriter.Workbook('/tmp/' + xls_filename)
        worksheet = workbook.add_worksheet("iBanking")
        ibanking_info = self.get_ibanking_list()
        # report_stock_inv_obj = self.env['report.stock.report_stock_inventory']

        # Format
        header_merge_format = workbook.add_format(
            {'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 10,
             'bg_color': '#D3D3D3', 'border': 1})
        header_data_format = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'font_size': 10, 'border': 1})
        product_header_format = workbook.add_format({'valign': 'vcenter', 'font_size': 10, 'border': 1})

        # Initial value
        rows = 2
        # warehouse_qty = len(self.warehouse_ids)
        # ------------------------------------------------------------------

        if self.bank == 'aba':
            # Start of main table
            for line in ibanking_info:
                warehouse_col = 3
                total_beginning_qty = total_qty_in = total_qty_out = total_qty_internal = total_ending_qty = 0.00
                # for warehouse in self.warehouse_ids:

                # ------------------------------ Main Table Header --------------------------------

                worksheet.write(1, 0, "Employee Name", header_merge_format)
                worksheet.write(1, 1, "Employee Id", header_merge_format)
                worksheet.write(1, 2, "Account Number", header_merge_format)
                worksheet.write(1, 3, "Amount", header_merge_format)

                # --------------------------------- Display Total --------------------------------
                worksheet.write(rows, 0, line['name'], header_data_format)

                worksheet.write(rows, 1, line['id'], header_data_format)
                worksheet.write(rows, 2, line['bank_number'], header_data_format)

                worksheet.write(rows, 3, line['amount'], header_data_format)
                # --------------------------------------------------------------------------------
                rows += 1

        if self.bank == 'acleda':
            # Start of main table
            for line in ibanking_info:
                warehouse_col = 3
                total_beginning_qty = total_qty_in = total_qty_out = total_qty_internal = total_ending_qty = 0.00
                # for warehouse in self.warehouse_ids:

                # ------------------------------ Main Table Header --------------------------------

                worksheet.write(1, 0, "No", header_merge_format)
                worksheet.write(1, 1, "Credit Account No", header_merge_format)
                worksheet.write(1, 2, "Name", header_merge_format)
                worksheet.write(1, 3, "Currency", header_merge_format)
                worksheet.write(1, 4, "Amount", header_merge_format)
                worksheet.write(1, 5, "Value Date", header_merge_format)
                worksheet.write(1, 6, "Narrative", header_merge_format)

                # --------------------------------- Display Total --------------------------------
                worksheet.write(rows, 0, line['no'], header_data_format)
                worksheet.write(rows, 1, line['bank_number'], header_data_format)
                worksheet.write(rows, 2, line['name'], header_data_format)
                worksheet.write(rows, 3, line['currency'], header_data_format)
                worksheet.write(rows, 4, line['amount'], header_data_format)
                worksheet.write(rows, 5, line['date'], header_data_format)
                worksheet.write(rows, 6, line['narrative'], header_data_format)
                # --------------------------------------------------------------------------------
                rows += 1

        if self.bank == 'chipmong':
            # Start of main table
            for line in ibanking_info:
                warehouse_col = 3
                total_beginning_qty = total_qty_in = total_qty_out = total_qty_internal = total_ending_qty = 0.00
                # for warehouse in self.warehouse_ids:

                # ------------------------------ Main Table Header --------------------------------

                worksheet.write(1, 0, "0025749", header_merge_format)
                worksheet.write(1, 1, "77889977", header_merge_format)
                worksheet.write(1, 2, "3480.30", header_merge_format)
                worksheet.write(1, 3, "USD", header_merge_format)

                # --------------------------------- Display Total --------------------------------
                worksheet.write(rows, 0, line['name'], header_data_format)

                worksheet.write(rows, 1, line['id'], header_data_format)
                worksheet.write(rows, 2, line['bank_number'], header_data_format)

                worksheet.write(rows, 3, line['amount'], header_data_format)
                # --------------------------------------------------------------------------------
                rows += 1
        
        if self.bank == 'vattanac':
            # Start of main table
            for line in ibanking_info:
                warehouse_col = 3
                total_beginning_qty = total_qty_in = total_qty_out = total_qty_internal = total_ending_qty = 0.00
                # for warehouse in self.warehouse_ids:

                # ------------------------------ Main Table Header --------------------------------

                # worksheet.write(1, 0, "No", header_merge_format)
                worksheet.write(1, 1, "ToSalaryAccount", header_merge_format)
                worksheet.write(1, 2, "ToSalaryAccountName", header_merge_format)
                worksheet.write(1, 4, "SalaryAmount", header_merge_format)
                worksheet.write(1, 3, "SalaryCurrency", header_merge_format)
                # worksheet.write(1, 5, "Value Date", header_merge_format)
                # worksheet.write(1, 6, "Narrative", header_merge_format)6

                # --------------------------------- Display Total --------------------------------
                # worksheet.write(rows, 0, line['no'], header_data_format)
                worksheet.write(rows, 1, line['bank_number'], header_data_format)
                worksheet.write(rows, 2, line['name'], header_data_format)
                worksheet.write(rows, 4, line['amount'], header_data_format)
                worksheet.write(rows, 3, line['currency'], header_data_format)
                # worksheet.write(rows, 5, line['date'], header_data_format)
                # worksheet.write(rows, 6, line['narrative'], header_data_format)
                # --------------------------------------------------------------------------------
                rows += 1

        workbook.close()
        self.write({
            'state': 'get',
            'data': base64.b64encode(open('/tmp/' + xls_filename, 'rb').read()),
            'name': xls_filename
        })
        return {
            'name': 'iBanking Report',
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new'
        }
