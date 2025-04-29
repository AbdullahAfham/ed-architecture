from odoo import api, fields, models, _
from datetime import datetime
from odoo.exceptions import UserError


class VisitHistory(models.Model):
    _name = 'visit.history'
    _description = 'Visit History'

    salesperson_id = fields.Many2one('res.users', string='Salesperson', required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    visit_duration = fields.Float(string='Duration', compute='_compute_visit_duration')
    display_visit_duration = fields.Char(string='Duration', compute='_compute_display_visit_duration')
    date = fields.Date(string='Date', required=True)

    visit_location_ids = fields.One2many('visit.history.location', 'visit_history_id', string='Locations')

    def unlink(self):
        """ OVERRIDE: returns a clear, concise error message. """
        if self.visit_location_ids.exists():
            raise UserError(_("Visit History contains Check In/Check Out records."))
        
        return super().unlink()

    def _compute_visit_duration(self):
        for history in self:
            all_visit_date = history.visit_location_ids.mapped('visit_datetime')

            if not all_visit_date:
                history.visit_duration = 0
                continue
            
            duration = max(all_visit_date) - min(all_visit_date)
            history.visit_duration = duration.total_seconds() / 3600  # convert seconds to hours

    def _compute_display_visit_duration(self):
        for history in self:
            total_minutes = int(history.visit_duration * 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60

            parts = []
            if hours:
                parts.append(f"{hours}h")
            if minutes:
                parts.append(f"{minutes}mn")
    
            history.display_visit_duration = ' '.join(parts) if parts else "0mn"

    def create_or_update_visit_history(self, vals: dict):
        """ Create or Update `visit.history` of provided `vals`.

        :return: tuple containing:
            - visit_history: `visit.history` recordset.
            - is_updated: a flag indicate whether it is processed by creating or updating.
        """
        partner_id, date = vals.get('partner_id'), vals.get('date')

        if not partner_id or not date:
            raise UserError(_("Customer ID and Visit Date are required."))
        
        visit_history = self.search([('partner_id', '=', partner_id), ('date', '=', date)], limit=1)

        if not visit_history:
            # create if not exist
            visit_history = self.create(vals)
            is_updated = False
        else:
            # update `visit.history.location`
            visit_history.write({'visit_location_ids': vals.get('visit_location_ids')})
            is_updated = True

        return visit_history, is_updated

    def get_visit_locations(self):
        visit_location_data = []
        for visit_location in self.visit_location_ids:
            visit_location_data.append(
                {
                    'latitude': visit_location.latitude,
                    'longitude': visit_location.longitude,
                    'reason': visit_location.reason or "",
                    'datetime': visit_location.visit_datetime.strftime("%d-%m-%Y %H:%M:%S") or "",
                }
            )
        return visit_location_data


class VisitHistoryLocation(models.Model):
    _name = 'visit.history.location'
    _description = 'Visit History Location'

    @api.model
    def _get_default_visit_datetime(self):
        # TODO: handle timezone offset issue, to use `date` field of `visit.history ` with the current time
        now = datetime.now()
        visit_date = self.env.context.get('date', False)
        
        if not visit_date:
            return now
        
        visit_date = fields.Date.to_date(visit_date)
        return now.replace(year=visit_date.year, month=visit_date.month, day=visit_date.day)

    
    visit_history_id = fields.Many2one('visit.history', string='Visit History', required=True)
    visit_datetime = fields.Datetime(string='Date and Time', required=True, default=fields.Datetime.now)
    latitude = fields.Float(string='Latitude', digits=(10, 7))
    longitude = fields.Float(string='Longitude', digits=(10, 7))
    reason = fields.Char(string='Reason')

    @api.model_create_multi
    def create(self, vals_list):
        """ OVERRIDE """
        return super().create(vals_list)
    
    @api.model
    def _get_visit_history(self, partner_id, date) -> list:
        """ 
        :return: list of dict or empty list
        """
        visit_history_id = self.env['visit.history'].search([
            ('partner_id', '=', partner_id), 
            ('date', '=', date),
        ], limit=1)

        if not visit_history_id:
            return []
        
        visit_history = visit_history_id.visit_location_ids.read(
            ['visit_datetime', 'latitude', 'longitude']
        )
        return visit_history
