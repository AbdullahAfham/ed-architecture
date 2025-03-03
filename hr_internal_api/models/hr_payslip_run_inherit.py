from odoo import models
from odoo.addons.hr_internal_api.controller.send_notification import send_notification_multicast
import logging


class HrPayslipRunInherit(models.Model):
    _inherit = 'hr.payslip.run'

    def action_notify_release_payslip(self):
        try:
            # get all employee from payslip run
            employee_ids = self.sudo().slip_ids.mapped('employee_id')

            # get all device token from employee user
            device_tokens = employee_ids.mapped('user_id.device_token')

            # get all user id from employee user
            user_ids = employee_ids.mapped('user_id.id')

            # send notification to all employee user
            send_notification_multicast(
                title='Payslip Release',
                body='Your payslip has been released',
                device_tokens=device_tokens,
                user_ids=user_ids,
            )
            return True
        except Exception as e:
            logging.info('Error sending message')
            logging.info(e)
            return False
