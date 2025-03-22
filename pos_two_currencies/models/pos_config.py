# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, Command
from odoo.exceptions import ValidationError
import pytz

class PosConfigInherit(models.Model):
    _inherit = 'pos.config'

    exchange_rate = fields.Float(string='Exchange Rate', compute='_compute_exchange_rate')
    last_session_closing_cash_khr = fields.Float(compute='_compute_last_session')
    iface_disc_button = fields.Boolean(string='Discount All Button')
    currency_khr = fields.Many2one('res.currency', string='Currency KHR', default=lambda self: self.env.ref("base.KHR", raise_if_not_found=False).id, limit=1)
    is_one_currency = fields.Boolean(string='One Currency', compute='_compute_is_one_currency')
    is_khr_currency = fields.Boolean(string='KHR Currency', compute='_compute_is_khr_currency')
    discount_product_id = fields.Many2one('product.product', string='Discount Product',
                                          domain=[('sale_ok', '=', True)],
                                          help='The product used to apply the discount on the ticket.')

    @api.depends('payment_method_ids')
    def _compute_is_one_currency(self):
        for config in self:
            config.is_one_currency = len(config.payment_method_ids.filtered('is_cash_count')) < 2

    @api.depends('is_one_currency', 'payment_method_ids')
    def _compute_is_khr_currency(self):
        for config in self:
            if config.is_one_currency:
                config.is_khr_currency = any(config.payment_method_ids.mapped(lambda m: m.is_cash_count and m.name and 'khr' in m.name.lower()))
            else:
                config.is_khr_currency = False

    def get_order_sequence_number(self):
        sequence_id = self.sequence_id
        return sequence_id.get_next_char(sequence_id.number_next_actual)

    @api.depends('session_ids')
    def _compute_last_session(self):
        PosSession = self.env['pos.session']
        for pos_config in self:
            sessions = PosSession.search_read(
                [('config_id', '=', pos_config.id), ('state', '=', 'closed')],
                ['cash_register_balance_end_real', 'stop_at', 'cash_register_balance_end_real_khr'],
                order="stop_at desc", limit=1)
            timezone = pytz.timezone(self._context.get('tz') or self.env.user.tz or 'UTC')
            session = sessions[0] if sessions else False
            if session:
                pos_config.last_session_closing_date = session['stop_at'] and session['stop_at'].astimezone(timezone) or False
                pos_config.last_session_closing_cash = session['cash_register_balance_end_real']
                pos_config.last_session_closing_cash_khr = session['cash_register_balance_end_real_khr']
            else:
                pos_config.last_session_closing_cash = 0
                pos_config.last_session_closing_cash_khr = 0
                pos_config.last_session_closing_date = False

    @api.depends('currency_khr.rate')
    def _compute_exchange_rate(self):
        for config in self:
            config.exchange_rate = self.currency_khr and self.currency_khr.rate or 4000

    def get_tables_order_count(self):
        self.ensure_one()
        res = super(PosConfigInherit, self).get_tables_order_count()
        return {
            "exchange_rate": self.exchange_rate,
            "result": res
        }

    @api.constrains('pricelist_id', 'use_pricelist', 'available_pricelist_ids', 'journal_id', 'invoice_journal_id', 'payment_method_ids')
    def _check_currencies(self):
        for config in self:
            if config.use_pricelist and config.pricelist_id and config.pricelist_id not in config.available_pricelist_ids:
                raise ValidationError(_("The default pricelist must be included in the available pricelists."))

            # Dev: Allow different currency for payment methods
            # Check if the config's payment methods are compatible with its currency
            # for pm in config.payment_method_ids:
            #     if pm.journal_id and pm.journal_id.currency_id and pm.journal_id.currency_id != config.currency_id:
            #         raise ValidationError(_("All payment methods must be in the same currency as the Sales Journal or the company currency if that is not set."))

            if config.use_pricelist and config.pricelist_id and any(config.available_pricelist_ids.mapped(lambda pricelist: pricelist.currency_id != config.currency_id)):
                raise ValidationError(_("All available pricelists must be in the same currency as the company or"
                                        " as the Sales Journal set on this point of sale if you use"
                                        " the Accounting application."))
            if config.invoice_journal_id.currency_id and config.invoice_journal_id.currency_id != config.currency_id:
                raise ValidationError(_("The invoice journal must be in the same currency as the Sales Journal or the company currency if that is not set."))

    @api.constrains('payment_method_ids')
    def _check_payment_method_ids_journal(self):
        pass
        # Dev: Allow same payment cash methods for each POS
        # for cash_method in self.payment_method_ids.filtered(lambda m: m.journal_id.type == 'cash'):
        #     if self.env['pos.config'].search([('id', '!=', self.id), ('payment_method_ids', 'in', cash_method.ids)]):
        #         raise ValidationError(_("This cash payment method is already used in another Point of Sale.\n"
        #                                 "A new cash payment method should be created for this Point of Sale."))
        #     if len(cash_method.journal_id.pos_payment_method_ids) > 1:
        #         raise ValidationError(_("You cannot use the same journal on multiples cash payment methods."))
