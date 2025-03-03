from odoo import api, fields, models


class ProjectInherit(models.Model):
    _inherit = "project.project"

    project_name = fields.Char(string='Project Name')
    