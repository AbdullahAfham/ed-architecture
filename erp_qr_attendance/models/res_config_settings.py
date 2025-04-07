from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    late_buffer_duration = fields.Char(
        string='Late Buffer',
        default=15,
        config_parameter='erp_qr_attendance.late_buffer_duration'
    )
    checkin_late = fields.Boolean(
        string='Check In Late',
        default=True,
        config_parameter='erp_qr_attendance.is_checkin_late'
    )
    checkout_early = fields.Boolean(
        string='Check Out Early',
        default=False,
        config_parameter='erp_qr_attendance.is_checkout_early'
    )
    breakin_late = fields.Boolean(
        string='Break In Late',
        default=True,
        config_parameter='erp_qr_attendance.is_breakin_late'
    )
    breakout_early = fields.Boolean(
        string='Break Out Early',
        default=True,
        config_parameter='erp_qr_attendance.is_breakout_early'
    )
    scan_break = fields.Boolean(
        string='Break',
        default=False,
        config_parameter='erp_qr_attendance.scan_break'
    )
    late_create_time_off = fields.Boolean(
        string='Late Create Time Off',
        default=False,
        config_parameter='erp_qr_attendance.late_create_time_off'
    )
    late_time_off_type_id = fields.Many2one(
        'hr.leave.type',
        string='Time Off Type',
        config_parameter='erp_qr_attendance.late_time_off_type_id'
    )
    missing_create_time_off = fields.Boolean(
        string='Missing Create Time Off',
        default=False,
        config_parameter='erp_qr_attendance.missing_create_time_off'
    )
    missing_time_off_type_id = fields.Many2one(
        'hr.leave.type',
        string='Time Off Type',
        config_parameter='erp_qr_attendance.missing_time_off_type_id'
    )
    absence_create_time_off = fields.Boolean(
        string='Absence Create Time Off',
        default=False,
        config_parameter='erp_qr_attendance.absence_create_time_off'
    )
    absence_time_off_type_id = fields.Many2one(
        'hr.leave.type',
        string='Time Off Type',
        config_parameter='erp_qr_attendance.absence_time_off_type_id'
    )
