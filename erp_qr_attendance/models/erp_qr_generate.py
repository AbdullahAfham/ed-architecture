# -*- coding: utf-8 -*-
# Required lib: pip install pyqrcode
# Generate QR Image: pip install "qrcode[pil]"

from odoo import models, fields, api

try:
	import qrcode
except ImportError:
	qrcode = None

try:
	import base64
except ImportError:
	base64 = None

from io import BytesIO
from math import sin, cos, sqrt, atan2, radians

import uuid


class QRGenerate(models.Model):
	_name = 'erp.qr.generate'
	_description = "QR Generate"
	_inherit = ['mail.thread', 'mail.activity.mixin']

	name = fields.Char("Reference")
	project_id = fields.Many2one('project.project', string="Project")
	location_id = fields.Many2one('res.partner', string="Location")
	resource_calendar_id = fields.Many2one('resource.calendar', string="Working Schedule")
	longitude = fields.Float(string="Geo Longitude", copy=True, digits=(10, 14))
	latitude = fields.Float(string="Geo Latitude", copy=True, digits=(10, 14))
	radius = fields.Float(string='Valid Range (m)')
	description = fields.Html(string="Description")
	qr_code_uuid = fields.Char("UUID")
	qr_code_img = fields.Image("QR Code", max_width=1024, max_height=1024, store=True, copy=False)
	qr_code_name = fields.Char("Name")
	date_localization = fields.Date("Updated QR On")
	color = fields.Integer('Color Index')
	priority = fields.Selection([
		('0', 'Normal'),
		('1', 'Favorite'),
	], default='0', string="Favorite")

	def action_generate_qrcode(self):
		data = str(uuid.uuid4())

		if qrcode and base64:
			qr = qrcode.QRCode(
				version=1,
				error_correction=qrcode.constants.ERROR_CORRECT_L,
				box_size=3,
				border=4,
			)
			qr.add_data(data)
			qr.make(fit=True)
			img = qr.make_image()
			temp = BytesIO()
			img.save(temp, format="PNG")
			qr_image = base64.b64encode(temp.getvalue())

			self.write({'qr_code_img': qr_image, 'qr_code_uuid': data})

	@api.depends('name','project_id','longitude','latitude')
	def update_information(self):
		self.action_generate_qrcode()

	def geo_localize(self):
		# We need country names in English below
		for qr in self.with_context(lang='en_US'):
			result = self._geo_localize(
				qr.location_id.street,
				qr.location_id.zip,
				qr.location_id.city,
				qr.location_id.state_id.name,
				qr.location_id.country_id.name)

			if result:
				qr.write({
					'latitude': result[0],
					'longitude': result[1],
					'date_localization': fields.Date.context_today(qr)
				})

	def get_distance(self, lat, lon):
		# Approximate radius of earth in km
		R = 6373.0

		qr_lat = radians(self.latitude)
		qr_lon = radians(self.longitude)
		user_lat = radians(lat)
		user_lon = radians(lon)

		dlat = user_lat - qr_lat
		dlon = user_lon - qr_lon

		a = sin(dlat / 2) ** 2 + cos(qr_lat) * cos(user_lat) * sin(dlon / 2) ** 2
		c = 2 * atan2(sqrt(a), sqrt(1 - a))

		distance = R * c

		distance_in_meter = distance * 1000

		return distance_in_meter

	def get_qr_info(self):
		return {
			'id': self.id,
			'name': self.name,
			'project_id': self.project_id,
			'longitude': self.longitude,
			'latitude': self.latitude,
			'radius': self.radius,
		}
