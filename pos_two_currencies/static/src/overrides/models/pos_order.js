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

patch(PosOrder.prototype, {
    setup(_defaultObj, options) {
        super.setup(...arguments);
        this.is_khr = this.is_khr || false;
        this.discount_all = this.discount_all || false;
    },
    formatMonetaryKHR(val, hasSymbol = true) {
        return formatMonetary(val, { currencyId: this.pos.currency_khr?.id || false, noSymbol: !hasSymbol });
    },
    get_customer_display_orderlines() {
        return this.orderlines.filter((line) => !line.comboParent);
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
    getKHR() {
        const khr = this.get_total_khr();
        const currency_khr = this.pos.currency_khr ? this.pos.currency_khr : this.pos.currency;
        const symbol = currency_khr?.symbol || '';
        return this.pos.formatCurrencyKHR(khr);
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
        return round_pr(
            this.orderlines.reduce(function (sum, orderLine) {
                return sum + orderLine.get_all_prices().priceWithTaxBeforeDiscount;
            }, 0),
            this.pos.currency.rounding
        );
    },
    get_total_with_tax_before_discount_khr() {
        const total = this.get_total_with_tax_before_discount();
        const exchange_rate = this.config.exchange_rate;
        const total_khr = total ? round_pr(total*exchange_rate, 0) : 0;
        const khr = total ? round_pr(total_khr, 100) : 0;
        return khr;
    },
    export_as_JSON(){
        var json = super.export_as_JSON(...arguments);
        json.is_khr = this.is_khr;
        json.discount_all = this.discount_all;
        json.order_no = this.order_no;
        json.order_name = this.order_name;
        json.origs_order_name = this.origs_order_name;
        return json;
    },
    export_for_printing() {
        let json = super.export_for_printing(...arguments);
        var company = this.pos.company;
        const json_company = {
            email: company.email,
            website: company.website,
            company_registry: company.company_registry,
            contact_address: company.partner_id[1],
            vat: company.vat,
            vat_label: company.country && company.country.vat_label || _t('Tax ID'),
            name: company.name,
            phone: company.phone,
            logo:  this.pos.company_logo_base64,
            kh_name: company.kh_name,
            address_kh: company.address_kh,
        };

        return {
            ...json,
            amount_total_before_discount: this.get_total_with_tax_before_discount(),
            amount_total_before_discount_khr: this.get_total_with_tax_before_discount_khr(),
            amount_total_khr: this.get_total_khr(),
            khr_rate: this.pos.config.exchange_rate,
            order_name: this.order_name,
            changeUSD: this.changeText(),
            changeKHR: this.changeTextkhr(),
            // barcodeUrl: this.getBarcodeUrl(this.origs_order_name || this.uid),
            origs_order_name: this.origs_order_name || false,
            name: this.uid,
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
        var self = this;
        var lines = this.payment_ids;
        return round_pr(lines.reduce((function(sum, paymentLine) {
            var amount = paymentLine.get_amount();
            if (self.pos.is_usd){
                const exchange_rate = self.config.exchange_rate;
                // const currency_khr = self.pos.self ? paymentLine.pos.currency_khr : self.pos.currency;
                if (paymentLine.payment_method.name.includes("KHR")) {
                    amount = round_pr(amount/exchange_rate, 0.01)
                }
            }
            if (paymentLine.is_done()) {
                sum += amount;
            }
            return sum;
        }), 0), this.currency.rounding);
    },
    is_paid() {
        let allow_diff = 0;
        var lines = this.payment_ids;
        if (lines.some((paymentLine) => paymentLine.payment_method.name.includes("KHR"))) {
             // Dev: Allow Maximum diff is 40R
            allow_diff = 0.01;
        }
        return this.get_due() <= allow_diff && this.check_paymentlines_rounding();
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
                    if (this.pos.is_usd){
                        const exchange_rate = paymentline.pos.config.exchange_rate;
                        if (paymentline.payment_method.name.includes("KHR")) {
                            amount = round_pr(amount/exchange_rate,0.01)
                        }
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
            var change = this.get_total_paid() - this.get_total_with_tax() - this.get_rounding_applied();
        } else {
            var change = -this.get_total_with_tax();
            const exchange_rate = self.config.exchange_rate;
            const currency_khr = self.pos.currency_khr ? self.pos.currency_khr : self.pos.currency;
            var lines = this.payment_ids;
            for (var i = 0; i < lines.length; i++) {
                var amount = lines[i].get_amount();
                if (paymentline.payment_method.name.includes("KHR")&&this.pos.is_usd){
                    amount = round_pr(amount/exchange_rate,0.01)
                }
                change +=amount;
                if (lines[i] === paymentline) {
                    break;
                }
            }
        }
        return round_pr(Math.max(0,change), 0.01);
    },
    changeTextkhr() {
        var change = this.locked ? this.amount_return : this.get_change();
        const currency_khr = this.pos.currency_khr ? this.pos.currency_khr : this.pos.currency;
        const exchange_rate = this.pos.config.exchange_rate;
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
        var change = this.locked ? this.amount_return : this.get_change();
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
            if(payment_method.name.includes("KHR") && this.pos.is_usd){
                due = round_pr(due*exchange_rate, 1)
            }
            newPaymentline.set_amount(due);

            this.payment_ids.add(newPaymentline);
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
