from odoo import models

class MailMail(models.Model):
    _inherit = "mail.mail"

    def send(self, auto_commit=False, raise_exception=False):
        for mail in self:
            if mail.email_cc:
                # Make sure CC is included in actual recipients too
                if mail.email_to:
                    mail.email_to = f"{mail.email_to},{mail.email_cc}"
                else:
                    mail.email_to = mail.email_cc
        return super().send(auto_commit=auto_commit, raise_exception=raise_exception)
