from odoo import api, fields, models


class ProjectInherit(models.Model):
    _inherit = "project.project"


    def _compute_budgets(self):
        for project in self:
            project.budget_actual = sum(project.timesheet_ids.mapped('amount'))
            project.balance = project.budget_plan + project.budget_actual

    user_id = fields.Many2one('res.users', string='Project Manager', default=lambda self: self.env.user, tracking=True,
                              required=True)
    hr_manager_id = fields.Many2one('res.users', string='HR Manager', tracking=True, required=True)
    om_id = fields.Many2one('res.users', string='General Lead', tracking=True, required=True)
    budget_plan = fields.Float('Budget Plan')
    budget_actual = fields.Float('Budget Actual', compute="_compute_budgets")
    balance = fields.Float('Balance', compute="_compute_budgets")

