from odoo import api, models, fields, _


class HrPaySlipRunInherit(models.Model):
    _inherit = 'hr.payslip.run'

    total_basic_wage = fields.Float(compute='_compute_total_wage', string="Total Basic Wage")
    total_addition = fields.Float(compute='_compute_total_wage', string="Total Addition")
    total_deduction = fields.Float(compute='_compute_total_wage', string="Total Deduction")
    total_unpaid = fields.Float(compute='_compute_total_wage', string="Total Unpaid")
    total_gross = fields.Float(compute='_compute_total_wage', string="Total Gross")
    total_net_wage = fields.Float(compute='_compute_total_wage', string="Total Net Wage")

    @api.depends('slip_ids.line_ids')
    def _compute_total_wage(self):
        for record in self:
            lines = record.slip_ids.line_ids.filtered(
                lambda line: line.code in [
                    'BASIC', 'ALW', 'DEDUCTION', 'UNPAID', 'GROSS', 'NET',
                ]
            )

            record.total_basic_wage = sum(
                lines.filtered(lambda line: line.code == 'BASIC').mapped('total')
            )
            record.total_addition = sum(
                lines.filtered(lambda line: line.code == 'ALW').mapped('total')
            )
            record.total_deduction = sum(
                lines.filtered(lambda line: line.code == 'DEDUCTION').mapped('total')
            )
            record.total_unpaid = sum(
                lines.filtered(lambda line: line.code == 'UNPAID').mapped('total')
            )
            record.total_gross = sum(
                lines.filtered(lambda line: line.code == 'GROSS').mapped('total')
            )
            record.total_net_wage = sum(
                lines.filtered(lambda line: line.code == 'NET').mapped('total')
            )
            


class HrPaySlipInherit(models.Model):
    _inherit = "hr.payslip"

    addition = fields.Float(compute='_compute_total', string="Addition", store=True)
    deduction = fields.Float(compute='_compute_total', string="Deduction", store=True)
    unpaid = fields.Float(compute='_compute_total', string="Unpaid", store=True)
    
    @api.depends('line_ids')
    def _compute_total(self):
        for payslip in self:
            lines = payslip.line_ids.filtered(lambda line: line.code in [
                'ALW', 'DEDUCTION', 'UNPAID',
            ])
                                                                         
            payslip.addition = sum(lines.filtered(lambda line: line.code == 'ALW').mapped('total'))
            payslip.unpaid = sum(lines.filtered(lambda line: line.code == 'UNPAID').mapped('total'))
            payslip.deduction = sum(lines.filtered(lambda line: line.code == 'DEDUCTION').mapped('total'))
            