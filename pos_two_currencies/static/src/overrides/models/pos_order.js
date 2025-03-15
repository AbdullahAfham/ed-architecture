/** @odoo-module */

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { formatMonetary } from "@web/views/fields/formatters";
import {
    roundDecimals as round_di,
    roundPrecision as round_pr,
    floatIsZero,
} from "@web/core/utils/numbers";
import {
    deserializeDate,
    formatDateTime,
} from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { lt } from "@point_of_sale/utils";
import { omit } from "@web/core/utils/objects";

patch(PosOrder.prototype, {
    setup(_defaultObj, options) {
        super.setup(...arguments);
        this.is_khr = this.is_khr || false;
        this.discount_all = this.discount_all || false;
    },
    formatMonetaryKHR(val, hasSymbol = true) {
        return formatMonetary(val, { currencyId: this.currencyKHR || false, noSymbol: !hasSymbol });
    },
    get_customer_display_orderlines() {
        return this.lines.filter((line) => !line.comboParent);
    },
    get currencyKHR() {
        return this.models["res.currency"].find((currency) => currency.name === "KHR");
    },
    getOrderDate() {
        const now = luxon.DateTime.now();
        const date = this.date_order ? this.date_order : now;
        return formatDateTime(date, { format: 'dd-MM-yyyy hh:mm a' });
    },
    getBarcodeUrl(name, size=100) {
        // ?width=${size}&height=${size}
        return `/report/barcode/QR/${name}?width=${size}&height=${size}`;
    },
    formatCurrencyKHR(value, hasSymbol = true) {
        return formatMonetary(value, {
            currencyId: this.currency_khr && this.currency_khr.id || 66,
            noSymbol: !hasSymbol,
        });
    },
    getKHR() {
        const khr = this.get_total_khr();
        const currency_khr = this.currencyKHR || this.currency;
        const symbol = currency_khr?.symbol || '';
        return this.formatCurrencyKHR(khr);
    },
    init_from_JSON(json){
        super.init_from_JSON(...arguments);
        this.is_khr = json.is_khr;
        this.discount_all = json.discount_all;
        this.order_no = json.order_no;
        this.order_name = json.order_name;
        this.origs_order_name = json.origs_order_name || false;
    },
    get_total_with_tax_before_discount() {
        const self = this;
        const discount_product = self.config.discount_product_id;
        let orderlines = this.lines;
        if (discount_product && discount_product.id && orderlines.length) {
            orderlines = orderlines.filter((l) => l.product_id?.id !== discount_product.id)
        }
        return round_pr(
            orderlines.reduce(function (sum, orderLine) {
                let lineAllPriceUnit = orderLine.get_all_prices();
                return sum + (self.config.iface_tax_included === "total" ? lineAllPriceUnit.priceWithTaxBeforeDiscount : lineAllPriceUnit.priceWithoutTaxBeforeDiscount);
            }, 0),
            this.currency.rounding
        );
    },
    get_total_with_tax_before_discount_khr() {
        const total = this.get_total_with_tax_before_discount();
        const exchange_rate = this.config.exchange_rate;
        const total_khr = total ? round_pr(total*exchange_rate, 0) : 0;
        const khr = total ? round_pr(total_khr, 100) : 0;
        return khr;
    },
    get_total_discount() {
        let total_discount = super.get_total_discount(...arguments);
        const discount_product = this.config.discount_product_id;
        let orderlines = this.getSortedOrderlines();
        if (discount_product && discount_product.id && orderlines.length) {
            orderlines = orderlines.filter((l) => l.product_id?.id === discount_product.id)
            if (orderlines) {
                total_discount += orderlines.reduce(function (sum, orderLine) {
                    return sum + (orderLine.get_display_price() * -1); // DEV: Discount line is Minus amount
                }, 0);
            }
        }
        return total_discount;
    },
    export_for_printing() {
        let json = super.export_for_printing(...arguments);
        const company = this.company;
        const json_company = {
            email: company.email,
            website: company.website,
            company_registry: company.company_registry,
            contact_address: company.partner_id[1],
            vat: company.vat,
            vat_label: company.country && company.country.vat_label || _t('Tax ID'),
            name: company.name,
            phone: company.phone,
            logo:  this.company_logo_base64,
            kh_name: company.kh_name,
            address_kh: company.address_kh,
        };
        const discount_product = this.config.discount_product_id;
        let orderlines = this.getSortedOrderlines();
        if (discount_product && discount_product.id && orderlines.length) {
            orderlines = orderlines.filter((l) => l.product_id?.id !== discount_product.id)
        }

        return {
            ...json,
            orderlines: orderlines.map((l) =>
                omit(l.getDisplayData(), "internalNote")
            ),
            amount_total_before_discount: this.get_total_with_tax_before_discount(),
            amount_total_before_discount_khr: this.get_total_with_tax_before_discount_khr(),
            amount_total_khr: this.get_total_khr(),
            khr_rate: this.config.exchange_rate,
            // order_name: this.order_name,
            showTax: this.config.iface_tax_included !== "total",
            changeUSD: this.changeText(),
            changeKHR: this.changeTextkhr(),
            // barcodeUrl: this.getBarcodeUrl(this.origs_order_name || this.uid),
            // origs_order_name: this.origs_order_name || false,
            name: this.pos_reference,
            order_name: this.name,
            company: json_company,
        };
    },
    set_origs_order_name(name){
        this.origs_order_name = name;
    },
    set_order_name(order_name){
        this.order_name = order_name;
    },
    generate_order_sequence(sequence) {
        function zero_pad(num,size){
            var s = ""+num;
            while (s.length < size) {
                s = "0" + s;
            }
            return s;
        }

        if (!sequence) {
            return '';
        }
        return sequence.prefix + zero_pad(sequence.number, sequence.padding);
    },
    get_total_paid() {
        const self = this;
        return round_pr(
            self.payment_ids.reduce(function (sum, paymentLine) {
                let amount = paymentLine.get_amount();
                const exchange_rate = self.config.exchange_rate;
                // [DEV]: Already convert when validate payment
                if ((self.state === "draft")&& paymentLine.payment_method_id.name.toUpperCase().includes("KHR")) {
                    amount = round_pr(amount / exchange_rate, self.currency.rounding)
                }
                if (paymentLine.is_done()) {
                    sum += amount;
                }
                return sum;
            }, 0),
            this.currency.rounding
        );
    },
    is_paid() {
        let allow_diff = 0;
        const lines = this.payment_ids;
        if (lines.some((paymentLine) => paymentLine.payment_method_id.name.toUpperCase().includes("KHR"))) {
             // Dev: Allow Maximum diff is 40R
            allow_diff = 0.01;
        }
        return this.get_due() <= allow_diff;
    },
    set_is_khr (is_khr){
        this.is_khr = is_khr;
    },
    set_discount_all (discount){
        this.discount_all = discount;
    },
    get_discount_all (){
        return this.discount_all;
    },
    get_due(paymentline) {
        if (!paymentline) {
            var due = round_pr(this.get_total_with_tax(), this.currency.rounding) - round_pr(this.get_total_paid(), this.currency.rounding);
        } else {
            var due = round_pr(this.get_total_with_tax(), this.currency.rounding);
            var lines = this.payment_ids;
            for (var i = 0; i < lines.length; i++) {
                if (lines[i] === paymentline) {
                    break;
                } else {
                    var amount = lines[i].get_amount();
                    const exchange_rate = this.config.exchange_rate;
                    if (paymentline.payment_method_id.name.toUpperCase().includes("KHR")) {
                        amount = round_pr(amount/exchange_rate,0.01)
                    }
                    due -= round_pr(amount, this.currency.rounding);
                }
            }
        }
        return round_pr(due, this.currency.rounding);
    },
    get_change(paymentline) {
        const self = this;
        if (!paymentline) {
            var change =
                this.get_total_paid() - this.get_total_with_tax() - this.get_rounding_applied();
        } else {
            var change = -this.get_total_with_tax();
            const exchange_rate = self.config.exchange_rate;
            var lines = this.payment_ids;
            for (var i = 0; i < lines.length; i++) {
                var amount = lines[i].get_amount();
                if (paymentline.payment_method_id.name.toUpperCase().includes("KHR")){
                    amount = round_pr(amount/exchange_rate,0.01)
                }
                change +=amount;
                if (lines[i] === paymentline) {
                    break;
                }
            }
        }
        return round_pr(Math.max(0,change), this.currency.rounding);
    },
    changeTextkhr() {
        var change = this.amount_return;
        if (!this.finalized && !change) {
            change = this.get_change();
        }
        const exchange_rate = this.config.exchange_rate;
        var lines = this.payment_ids;
        var is_khr = this.is_khr;
        if(!is_khr) {
            if((lines.length > 0) && lines[lines.length-1].khr_last){
                is_khr=true;
            }
        }
        if(!is_khr){
            change = change - Math.floor(change/10)*10;
        }
        const khr = change ? round_pr(change*exchange_rate, 100) : 0;
        return khr;
    },
    changeText() {
        var change = this.amount_return;
        if (!this.finalized && !change) {
            change = this.get_change();
        }
        var lines = this.payment_ids;
        var is_khr = this.is_khr;
        if(!is_khr) {
            if((lines.length > 0) && lines[lines.length-1].khr_last){
                is_khr=true;
            }
        }
        if(is_khr){
            change = 0;
        }
        return Math.floor(change/10)*10;
    },
    get_total_with_tax() {
        return round_pr(
            this.lines.reduce((sum, orderLine) => {
                    sum += orderLine.get_all_prices().priceWithTax;
                return sum;
            }, 0),
            this.currency.rounding
        );
    },
    getTotalDue() {
        // return this.taxTotals.order_sign * this.taxTotals.order_total;
        return this.get_total_with_tax()
    },
    get_total_khr() {
        const total = this.get_total_with_tax();
        const exchange_rate = this.config.exchange_rate;
        const total_khr = total ? round_pr(total*exchange_rate, 0) : 0;
        const khr = total ? round_pr(total_khr, 100) : 0;
        return khr;
    },
    add_paymentline(payment_method) {
        this.assert_editable();
        if (this.electronic_payment_in_progress()) {
            return false;
        } else {
            const newPaymentline = this.models["pos.payment"].create({
                pos_order_id: this,
                payment_method_id: payment_method,
            });

            const exchange_rate = this.config.exchange_rate;
            var due = this.get_due();
            if(payment_method.name.toUpperCase().includes("KHR")){
                due = round_pr(due*exchange_rate, 1)
            }
            newPaymentline.set_amount(due);

            this.select_paymentline(newPaymentline);
            if (this.config.cash_rounding) {
                this.selected_paymentline.set_amount(0);
            }
            if (payment_method.payment_terminal) {
                newPaymentline.set_payment_status("pending");
            }
            return newPaymentline;
        }
    },
});
