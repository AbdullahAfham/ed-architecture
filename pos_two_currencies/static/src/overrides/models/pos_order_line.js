/** @odoo-module */

import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";

import { formatMonetary } from "@web/views/fields/formatters";
import { patch } from "@web/core/utils/patch";

patch(PosOrderline.prototype, {
    setup(obj, options) {
        super.setup(...arguments);
        var product = this.get_product();
        let is_discount_vat = false;
        if (product) {
            var taxes_ids = this.tax_ids || product.taxes_id;
            taxes_ids = taxes_ids.filter((t) => t in this.pos.taxes_by_id);
            var product_taxes = this.pos.get_taxes_after_fp(taxes_ids, this.order.fiscal_position);
            for (let i = 0; i < product_taxes.length; i++) {
                if (product_taxes[i].is_discount_vat === true) {
                    is_discount_vat = true;
                    break;
                }
            }
        }
        this.is_discount_vat = is_discount_vat;
    },
    init_from_JSON(json){
        super.init_from_JSON(...arguments);
        this.is_discount_vat = json.is_discount_vat;
    },
    export_as_JSON() {
        var json = super.export_as_JSON(...arguments);
        json.is_discount_vat = this.is_discount_vat;
        json.price_total_discount = this.getPriceTotalDiscount();
        return json;
    },
    export_for_printing() {
        var json = super.export_for_printing(...arguments);
        json.is_discount_vat = this.is_discount_vat;
        json.price_total_discount = this.getPriceTotalDiscount();
        return json;
    },
    set_is_discount_vat(is_discount_vat) {
        this.is_discount_vat = is_discount_vat;
    },
    getPriceTotalDiscount() {
        const all_prices = this.get_all_prices();
        return (all_prices.priceWithoutTaxBeforeDiscount - all_prices.priceWithoutTax) || 0;
    },
    getUnitDisplayPriceBeforeDiscount() {
        if (this.is_discount_vat) {
            return super.getUnitDisplayPriceBeforeDiscount(...arguments);
        }
        return this.get_all_prices(1).priceWithoutTaxBeforeDiscount;
    },
    get_all_prices(qty = this.get_quantity()) {
        if (this.is_discount_vat) {
            return super.get_all_prices(...arguments);
        }
        var price_unit = this.get_unit_price()
        var price_unit_discounted = price_unit * (1.0 - this.get_discount() / 100.0);
        var taxtotal = 0;

        var product = this.get_product();
        var taxes_ids = this.tax_ids || product.taxes_id;
        taxes_ids = taxes_ids.filter((t) => t in this.pos.taxes_by_id);
        var taxdetail = {};
        var product_taxes = this.pos.get_taxes_after_fp(taxes_ids, this.order.fiscal_position);

        var all_taxes = this.compute_all(
            product_taxes,
            price_unit_discounted,
            qty,
            this.pos.currency.rounding
        );
        var all_taxes_before_discount = this.compute_all(
            product_taxes,
            price_unit,
            qty,
            this.pos.currency.rounding
        );
        all_taxes_before_discount.taxes.forEach(function (tax) {
            taxtotal += tax.amount;
            taxdetail[tax.id] = {
                amount: tax.amount,
                base: tax.base,
            };
        });

        // let price_include = false;
        // for (let i = 0; i < product_taxes.length; i++) {
        //     if (product_taxes[i].price_include === true) {
        //         price_include = true;
        //         break;
        //     }
        // }
        const priceWithTax = all_taxes.total_excluded + taxtotal;
        // const priceWithoutTax = price_include ? all_taxes.total_included - taxtotal : all_taxes.total_excluded;
        const priceWithoutTax = all_taxes.total_excluded;

        return {
            priceWithTax: priceWithTax,
            priceWithoutTax: priceWithoutTax,
            priceWithTaxBeforeDiscount: all_taxes_before_discount.total_excluded + taxtotal,
            priceWithoutTaxBeforeDiscount: all_taxes_before_discount.total_excluded,
            tax: taxtotal,
            taxDetails: taxdetail,
        };
    },
    get_customer_display_price() {
        let price = this.get_display_price();
        if (this.comboLines?.length) {
            price += this.comboLines.reduce((sum, line) => sum + line.get_display_price(), 0);
        }
        return price;
    },
    getDisplayData() {
        let displayBorder = !this.isPartOfCombo();
        if (this.comboParent && this.comboParent.combo_line_ids?.length > 1) {
            const combo_line_ids = this.comboParent.combo_line_ids;
            // Display border on Last combo line
            displayBorder = combo_line_ids[combo_line_ids.length - 1] === this.id;
        }

        let price = this.get_display_price();
        let unitPrice = this.get_all_prices(1).priceWithTaxBeforeDiscount;
        if (this.comboLines?.length) {
            price += this.comboLines.reduce((sum, line) => sum + line.get_display_price(), 0);
            unitPrice += this.comboLines.reduce((sum, line) => sum + line.get_all_prices(1).priceWithTaxBeforeDiscount, 0);
        }

        return {
            ...super.getDisplayData(),
            displayBorder,
            priceNoSymbol: this.env.utils.formatCurrency(price, false),
            unitPriceNoSymbol: this.env.utils.formatCurrency(unitPrice, false),
        };
    },
});
