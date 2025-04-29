from odoo import _, api, fields, models


class CallPlans(models.Model):
    _name = 'call.plans'
    _description = 'Call Plans'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _track_duration_field = 'stage_id'

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        tracking=True
    )
    stage_id = fields.Many2one(
        comodel_name='call.plans.stages',
        string='Stage',
        store=True, index=True, readonly=False, tracking=True, copy=False,
        compute='_compute_stage_id',
        group_expand='_read_group_stage_ids',
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Contact',
        tracking=True,
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Responsible',
        tracking=True,
    )
    tag_ids = fields.Many2many(
        comodel_name='call.plans.tags',
        string='Tags',
        tracking=True,
    )
    plan_type_id = fields.Many2one(
        comodel_name='call.plans.types', string='Plan Type', tracking=True
    )
    name = fields.Char(
        string='Name', tracking=True
    )
    date = fields.Date(
        string='Date', tracking=True
    )
    date_start = fields.Datetime(
        string='Start Date', tracking=True
    )
    date_stop = fields.Datetime(
        string='End Date', tracking=True
    )
    image = fields.Binary(
        string='Image', tracking=True
    )
    color = fields.Integer(string='Color')
    partner_email = fields.Char(
        string='Email', tracking=True
    )
    partner_phone = fields.Char(
        string='Phone', tracking=True
    )
    active = fields.Boolean(
        string='Active', default=True, tracking=True
    )
    note = fields.Html(string='Notes')

    sequence = fields.Integer(string='Sequence')
    priority = fields.Boolean(string='Priority')
    kanban_state = fields.Selection([
        ('normal', 'In Progress'), 
        ('done', 'Ready'), 
        ('blocked', 'Blocked')], string="Kanban State",
        copy=False, default='normal', tracking=True
    )
    audit_trail = fields.Text(
        compute='_compute_audit_trail', string='Audit Trail'
    )

    attachment_ids = fields.One2many(
        'ir.attachment', 'res_id',
        string="Attachments",
        domain=lambda self: [('res_model', '=', self._name)]
    )

    def write(self, vals):
        # WIP: tracking html field in log note
        # if vals.get('note'):
        #     self.message_post(body_is_html=True, body=f"Description: {self.note} --> {vals['note']}")
        return super().write(vals)

    def copy_data(self, default=None):
        default = dict(default or {})
        vals_list = super().copy_data(default=default)
        if 'name' not in default:
            for plan, vals in zip(self, vals_list):
                vals['name'] = _("%s (copy)", plan.name)
        return vals_list

    @api.onchange('user_id')
    def onchange_user_company(self):
        current_user = self.env.user
        if current_user:
            self.company_id = current_user.company_id

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for call_plans in self:
            if not call_plans.partner_id:
                continue

            call_plans.partner_phone = call_plans.partner_id.phone
            call_plans.partner_email = call_plans.partner_id.email

    @api.depends('partner_id', 'user_id', 'plan_type_id')
    def _compute_stage_id(self):
        for call_plans in self:
            if not call_plans.stage_id:
                call_plans.stage_id = call_plans._stage_find(domain=[('fold', '=', False)]).id

    @api.model
    def _stage_find(self, domain=None, order='sequence, id', limit=1):
        """Determine the stage of the current record with the given domain."""
        search_domain = domain or []
        return self.env['call.plans.stages'].search(search_domain, order=order, limit=limit)

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        """Retrieve stage IDs for group expansion."""
        search_domain = ['|', ('id', 'in', stages.ids), ('fold', '=', False)]
        stage_ids = stages.sudo()._search(search_domain, order=stages._order)
        return stages.browse(stage_ids)
    
    def _compute_audit_trail(self):
        for record in self:
            audit_trail = ''
            for log in record.message_ids:
                if log.model == 'call.plans' and log.field_name in ['name', 'partner_id', 'user_id', 'partner_phone', 'partner_email', 'company_id', 'stage_id', 'image']:
                    audit_trail += f"{log.author_id.name} changed {log.field_name} from '{log.old_value_text}' to '{log.new_value_text}' on {log.date}\n"
            record.audit_trail = audit_trail

    def _get_next_stage(self):
        """ Determine the next stage of `call.plans`. It returns a dictionary representing a next stage.
        Otherwise, `None` will be returned if the current stage is the last one in the `call.plans.stages` sequence.
        """
        # fetch data
        stages = self.env['call.plans.stages'].search_read(domain=[], fields=["id", "name"])
        stage_ids = [s["id"] for s in stages]

        # get current stage id and index
        current_stage_id = self.stage_id.id
        current_stage_index = stage_ids.index(current_stage_id)

        # determine the next stage
        if current_stage_index + 1 < len(stages):
            next_stage = stages[current_stage_index + 1]
        else:
            next_stage = None

        return next_stage
