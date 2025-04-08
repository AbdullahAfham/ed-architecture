import datetime
from odoo import api, fields, models, _
from odoo.addons.hr_internal_api.controller.send_notification import send_notification_multicast, send_notification
from datetime import datetime, timedelta

class HrBatchOverTimeInherit(models.Model):
    _inherit = 'hr.batch.overtime'

    def submit_request(self):
        res = super(HrBatchOverTimeInherit, self).submit_request()
                
        start = self.date_from + timedelta(hours=7)
        end = self.date_to + timedelta(hours=7)
                    
        title = f"Batch Overtime Request from {self.create_uid.name}"
        body = f"Batch Overtime {self.name} from {start} to {end}"
        
        send_to = self.manager_id        
        if send_to and send_to.device_token:
            send_notification(
                title=title,
                body=body,
                device_token=send_to.device_token,
                user_id=send_to.id,
                link='/approve_batch_overtime/%s' % (self.id),
            )
        
        return True
    
class OvertimeInherit(models.Model):
    _inherit = 'hr.overtime'

    can_approve_overtime = fields.Boolean(string="Can Approve Overtime", default=False)

