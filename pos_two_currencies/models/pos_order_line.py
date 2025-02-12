# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    is_discount_vat = fields.Boolean(string='Discount VAT', default=False)
    price_total_discount = fields.Float(string='Total Discount', digits=0, readonly=True)

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields = super()._load_pos_data_fields(config_id)
        fields += ['is_discount_vat', 'price_total_discount']
        return fields

    def _is_product_kit_fifo_avco(self):
        self.ensure_one()
        return self.product_id.is_kits and self.product_id.cost_method in ['fifo', 'average']

    def _get_kit_stock_moves_to_consider(self, stock_moves, product):
        self.ensure_one()
        bom = product.env['mrp.bom']._bom_find(product, company_id=stock_moves.company_id.id, bom_type='phantom')[product]
        if not bom:
            return self._get_stock_moves_to_consider(stock_moves, product)
        _dummy, components = bom.explode(product, self.qty)
        ml_product_to_consider = (product.bom_ids and [comp[0].product_id.id for comp in components]) or [product.id]
        return stock_moves.filtered(lambda ml: ml.product_id.id in ml_product_to_consider and ml.bom_line_id and ml.bom_line_id.bom_id == bom)

    def _compute_kit_total_cost(self, stock_moves):
        self_sudo = self.sudo()
        for line in self.filtered(lambda l: l.is_total_cost_computed):
            product = line.product_id
            if line._is_product_kit_fifo_avco() and stock_moves:
                stock_moves_lines = line._get_kit_stock_moves_to_consider(stock_moves, product)
                product_cost = product._compute_average_price(0, line.qty, stock_moves_lines)
                if not float_compare(product_cost, 0, precision_rounding=line.currency_id.rounding):
                    bom = self_sudo.env['mrp.bom']._bom_find(product)[product]
                    if bom:
                        product_cost = product._compute_bom_price(bom, boms_to_recompute=False)
                    else:
                        bom = self_sudo.env['mrp.bom'].search([('byproduct_ids.product_id', '=', product.id)],
                                                            order='sequence, product_id, id', limit=1)
                        if bom:
                            product_cost = self_sudo._compute_bom_price(bom, boms_to_recompute=False, byproduct_bom=True)
                if not float_compare(product_cost, 0, precision_rounding=line.currency_id.rounding):
                    product_cost = product.product_cost
                line.total_cost = line.qty * product.cost_currency_id._convert(
                    from_amount=product_cost,
                    to_currency=line.currency_id,
                    company=line.company_id or self.env.company,
                    date=line.order_id.date_order or fields.Date.today(),
                    round=False,
                )
                line.is_total_cost_computed = True

    @api.onchange('qty', 'discount', 'price_unit', 'tax_ids')
    def _onchange_qty(self):
        # If the line is a discount VAT, we will use the default method
        if self.is_discount_vat:
            if self.product_id:
                self.price_total_discount =  self.price_unit * self.qty * ((self.discount or 0.0) / 100.0)
            return super(PosOrderLine, self)._onchange_qty()
        elif self.product_id:
            discount = ((self.discount or 0.0) / 100.0)
            price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
            self.price_subtotal = self.price_subtotal_incl = price * self.qty

            if (self.tax_ids):
                taxes_full = self.tax_ids.compute_all(self.price_unit, self.order_id.pricelist_id.currency_id, self.qty,
                                                      product=self.product_id, partner=False)
                taxes = self.tax_ids.compute_all(price, self.order_id.pricelist_id.currency_id, self.qty,
                                                 product=self.product_id, partner=False)
                taxes_full_amount = round(taxes_full['total_included'] - taxes_full['total_excluded'], 2)

                price_subtotal = taxes['total_excluded']
                self.price_subtotal = price_subtotal
                self.price_subtotal_incl = price_subtotal + taxes_full_amount
            else:
                price_subtotal = self.price_unit * self.qty
            self.price_total_discount = discount * price_subtotal

    def _compute_amount_line_all(self):
        self.ensure_one()

        # If the line is a discount VAT, we will use the default method
        if self.is_discount_vat:
            fpos = self.order_id.fiscal_position_id
            tax_ids_after_fiscal_position = fpos.map_tax(self.tax_ids)
            discount = ((self.discount or 0.0) / 100.0)
            price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
            taxes = tax_ids_after_fiscal_position.compute_all(price, self.order_id.currency_id, self.qty, product=self.product_id, partner=self.order_id.partner_id)
            return {
                'price_subtotal_incl': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
                'price_total_discount': discount * self.price_unit * self.qty,
            }

        fpos = self.order_id.fiscal_position_id
        tax_ids_after_fiscal_position = fpos.map_tax(self.tax_ids)
        discount = ((self.discount or 0.0) / 100.0)
        price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)

        taxes_full = tax_ids_after_fiscal_position.compute_all(self.price_unit, self.order_id.pricelist_id.currency_id,
                                                               self.qty, product=self.product_id,
                                                               partner=self.order_id.partner_id)
        taxes = tax_ids_after_fiscal_position.compute_all(price, self.order_id.pricelist_id.currency_id, self.qty,
                                                          product=self.product_id, partner=self.order_id.partner_id)
        taxes_full_amount = round(taxes_full['total_included'] - taxes_full['total_excluded'], 2)
        price_subtotal = taxes['total_excluded']

        return {
            'price_subtotal_incl': price_subtotal + taxes_full_amount,
            'price_subtotal': price_subtotal,
            'price_total_discount': discount * price_subtotal,
        }
