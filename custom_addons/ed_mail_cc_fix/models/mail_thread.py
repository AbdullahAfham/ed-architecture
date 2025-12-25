from odoo import models

class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def _message_get_smtp_headers(self, message):
        headers = super()._message_get_smtp_headers(message)
        if message.email_cc:
            headers["Cc"] = message.email_cc
        return headers
