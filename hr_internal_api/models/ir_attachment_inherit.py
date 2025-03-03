from odoo import models, fields


class AttachmentInherit(models.Model):
    _inherit = 'ir.attachment'

    leave_document_rel = fields.Many2many('hr.leave', string="Leave Document")
