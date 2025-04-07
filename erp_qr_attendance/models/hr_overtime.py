from odoo import models, fields

class HrOvertime(models.Model):
    _inherit = 'hr.overtime'

    def update_overtime_request(self):
        for hr_overtime in self:
            scan_logs = self.env['scan.qr.overtime'].search([
                ('employee_id', '=', hr_overtime.employee_id.id),
                ('date', '=', hr_overtime.date_from),
                ('status', '=', 'new')
            ])

            for rec in scan_logs:
                if rec.scan_type == 'ot_in':
                    if not hr_overtime.scan_ot_in:
                        hr_overtime.scan_ot_in = rec.scan_time
                        hr_overtime.update_scan_qr_overtime_status(rec)
                    elif hr_overtime.scan_ot_in > rec.scan_time:
                        continue
                    else:
                        rec.status = 'skip'
                elif rec.scan_type == 'ot_out':
                    if not hr_overtime.scan_ot_out:
                        hr_overtime.scan_ot_out = rec.scan_time
                        hr_overtime.update_scan_qr_overtime_status(rec)
                    elif hr_overtime.scan_ot_out < rec.scan_time:
                        continue
                    else:
                        rec.status = 'skip'

    def get_attendance_overtime(self):
        for hr_overtime in self:
            hr_overtime.update_overtime_request()

    def update_scan_qr_overtime_status(self, rec):
        rec.status = 'done'

        to_skip_scan_logs = self.env['scan.qr.overtime'].search([
            ('id', '!=', rec.id),
            ('employee_id', '=', rec.employee_id.id),
            ('date', '=', rec.date),
            ('scan_type', '=', rec.scan_type),
        ])
        to_skip_scan_logs.write({'status': 'skip'})
