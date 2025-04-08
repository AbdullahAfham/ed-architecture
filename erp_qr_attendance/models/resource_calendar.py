from odoo import api, models, fields, _
from datetime import datetime, timedelta
from odoo.exceptions import UserError


class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    is_cross_day_shift = fields.Boolean(
        string="Cross Day Shift", 
        default=False
    )
    is_night_shift = fields.Boolean(
        string="Night Shift", 
        default=False
    )

    scan_interval = fields.Float(
        string="Scan Interval", 
        help="This is the possible hours before `Work to` in order to scan `Check Out`."
    )

    def _find_day_period(self, scan_time=None):
        """ Find day period in which the given scan_time fall into.

        :param: datetime scan_time: its value is the current date and time if none.
        :return: `morning` or `afternoon` or `None`
        """
        if not scan_time:
            scan_time = datetime.now() + timedelta(hours=7)
        
        current_scan_time_float = self._get_scan_time_in_float(scan_time)

        dayofweek = scan_time.weekday()
        
        working_hours = self.attendance_ids.filtered(lambda a: a.dayofweek == str(dayofweek) and 
            a.x_studio_possible_work_from <= current_scan_time_float and
            a.x_studio_possible_work_to >= current_scan_time_float)
        
        return working_hours[-1].day_period if working_hours.exists() else None

    def _is_end_of_session(self, scan_time, day_period):
        """ Check whether the provided scan_time is ended for the day_period.
        
        :param: scan_time: an aware datetime object (means that its already +7 hours)
        :param: day_period: either `morning` or `afternoon`
        :return: boolean
        """
        current_scan_time_float = self._get_scan_time_in_float(scan_time)

        # returned the day of week as integer, where Monday is 0 and Sunday is 6.
        dayofweek = scan_time.weekday()

        working_hours = self.attendance_ids.filtered(
            lambda a: a.dayofweek == str(dayofweek) and a.day_period == day_period
        )

        # fix: in case of Sunday which usually not define in work schedule.
        # Hence, when the `dayofweek` of provided scan_time is not define in `working_hours`, use the previous day it found
        while not working_hours.exists():
            dayofweek -= 1
            
            working_hours = self.attendance_ids.filtered(
                lambda a: a.dayofweek == str(dayofweek) and a.day_period == day_period
            )

        if not working_hours.exists():
            raise UserError(_(f"Current Day of Week and Period not found in Working Schedule."))
                
        return current_scan_time_float >= working_hours.hour_to

    def _get_scan_time_in_float(self, scan_time):
        """ Convert the provided scan_time to float.

        :param: scan_time: an aware datetime object (means that its already +7 hours)
        :return: converted time in float
        """
        if isinstance(scan_time, datetime):
            current_scan_time = scan_time.time()
            hour, minute, second = str(current_scan_time).split(':')
            current_scan_time_float = float(hour) + float(minute) / 60.0

            return current_scan_time_float
