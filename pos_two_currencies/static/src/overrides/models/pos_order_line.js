/** @odoo-module */

import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";

import { formatMonetary } from "@web/views/fields/formatters";
import { patch } from "@web/core/utils/patch";
import {
    getTaxesAfterFiscalPosition,
    getTaxesValues,
} from "@point_of_sale/app/models/utils/tax_utils";

patch(PosOrderline.prototype, {
    setup(obj, options) {
        super.setup(...arguments);
        var product = this.get_product();
        let is_discount_vat = false;
        if (product) {
            let taxes = product.taxes_id;
            // Fiscal position.
            const order = this.order_id;
            if (order && order.fiscal_position_id) {
                taxes = getTaxesAfterFiscalPosition(taxes, order.fiscal_position_id, this.models);
            }

            for (let i = 0; i < taxes.length; i++) {
                if (taxes[i].is_discount_vat === true) {
                    is_discount_vat = true;
                    break;
                }
            }
        }
        this.is_discount_vat = is_discount_vat;
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
        const product = this.get_product();
        const priceUnit = this.get_unit_price();
        const discount = this.get_discount();
        const priceUnitAfterDiscount = priceUnit * (1.0 - discount / 100.0);

        let taxes = this.tax_ids || product.taxes_id;

        // Fiscal position.
        const fiscalPosition = this.order_id.fiscal_position_id;
        if (fiscalPosition) {
            taxes = getTaxesAfterFiscalPosition(taxes, fiscalPosition, this.models);
        }

        const taxesData = getTaxesValues(
            taxes,
            priceUnitAfterDiscount,
            qty,
            product,
            this.config._product_default_values,
            this.company,
            this.currency
        );
        const taxesDataBeforeDiscount = getTaxesValues(
            taxes,
            priceUnit,
            qty,
            product,
            this.config._product_default_values,
            this.company,
            this.currency
        );

        // Tax details.
        const taxDetails = {};
        let taxTotal = 0;
        for (const taxData of taxesData.taxes_data) {
            taxTotal += taxData.tax_amount;
            taxDetails[taxData.id] = {
                amount: taxData.tax_amount,
                base: taxData.base,
            };
        }

        const priceWithTax = taxesData.total_excluded + taxTotal;
        // const priceWithoutTax = price_include ? all_taxes.total_included - taxTotal : all_taxes.total_excluded;
        const priceWithoutTax = taxesData.total_excluded;

        return {
            priceWithTax: priceWithTax,
            priceWithoutTax: priceWithoutTax,
            // priceWithTax: taxesData.total_included,
            // priceWithoutTax: taxesData.total_excluded,
            priceWithTaxBeforeDiscount: taxesDataBeforeDiscount.total_included,
            priceWithoutTaxBeforeDiscount: taxesDataBeforeDiscount.total_excluded,
            tax: taxesData.total_included - taxesData.total_excluded,
            taxDetails: taxDetails,
            taxesData: taxesData.taxes_data,
        };
    },
    get_customer_display_price() {
        let price = this.get_display_price();
        if (this.comboLines?.length) {
            price += this.comboLines.reduce((sum, line) => sum + line.get_display_price(), 0);
        }
        return price;
    },
    // getDisplayData() {
    //     let displayBorder = !this.isPartOfCombo();
    //     if (this.comboParent && this.comboParent.combo_line_ids?.length > 1) {
    //         const combo_line_ids = this.comboParent.combo_line_ids;
    //         // Display border on Last combo line
    //         displayBorder = combo_line_ids[combo_line_ids.length - 1] === this.id;
    //     }
    //
    //     let price = this.get_display_price();
    //     let unitPrice = this.get_all_prices(1).priceWithTaxBeforeDiscount;
    //     if (this.comboLines?.length) {
    //         price += this.comboLines.reduce((sum, line) => sum + line.get_display_price(), 0);
    //         unitPrice += this.comboLines.reduce((sum, line) => sum + line.get_all_prices(1).priceWithTaxBeforeDiscount, 0);
    //     }
    //
    //     return {
    //         ...super.getDisplayData(),
    //         displayBorder,
    //         priceNoSymbol: this.env.utils.formatCurrency(price, false),
    //         unitPriceNoSymbol: this.env.utils.formatCurrency(unitPrice, false),
    //     };
    // },
});
