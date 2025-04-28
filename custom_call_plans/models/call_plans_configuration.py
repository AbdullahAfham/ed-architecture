from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CallPlanStages(models.Model):
    _name = 'call.plans.stages'
    _description = 'Call Plans Stages'
    _order = 'sequence, id'

    name = fields.Char(
        string='Stage Name', required=True
    )
    sequence = fields.Integer(
        string='Sequence', default=10
    )
    fold = fields.Boolean(
        string='Folded in Pipeline',
        help='This stage is folded in the kanban view when there are no records in that stage to display.'
    )
    is_first_stage = fields.Boolean(
        help="Identify whether the stage is the first one in flow."
    )
    is_last_stage = fields.Boolean(
        help="Identify whether the stage is the last one in flow."
    )
    display_stage = fields.Char(
        string="Used for", compute="_compute_display_stage"
    )

    def _compute_display_stage(self):
        for stage in self:
            values = []
            if stage.is_first_stage:
                values.append("First Stage")
            elif stage.is_last_stage:
                values.append("Last Stage")
            stage.display_stage = ", ".join(values) if values else ""

    call_plans_ids = fields.One2many(
        comodel_name='call.plans', inverse_name='stage_id', string='Call Plans'
    )


class CallPlanTags(models.Model):
    _name = 'call.plans.tags'
    _description = 'Call Plans Tags'

    name = fields.Char(string='Name', required=True)
    sequence = fields.Integer(string='Sequence', default=1)


class CallPlanTypes(models.Model):
    _name = 'call.plans.types'
    _description = 'Call Plans Types'

    name = fields.Char(string='Name', required=True)
    sequence = fields.Integer(string='Sequence', default=1)
    color = fields.Char(string="Color", default="#FF0000")
