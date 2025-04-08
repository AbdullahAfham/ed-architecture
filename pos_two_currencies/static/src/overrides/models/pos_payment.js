/** @odoo-module */

import { PosPayment } from "@point_of_sale/app/models/pos_payment";

import { formatMonetary } from "@web/views/fields/formatters";
import {
    roundDecimals as round_di,
    roundPrecision as round_pr,
    floatIsZero,
} from "@web/core/utils/numbers";
import { patch } from "@web/core/utils/patch";

patch(PosPayment.prototype, {
    setup(obj, options) {
        super.setup(...arguments);
        this.khr = this.khr || 0;
        this.khr_last = false;
        this.khr_name = this.khr_name || "CASH KHR";
    },
    get config() {
        return this.models["pos.config"].getFirst();
    },
    set_khr(payment_method, amount, khr_last) {
        const exchange_rate = this.config?.exchange_rate;
        if (payment_method.name.includes("KHR")) {
            const total_khr = round_pr(amount*exchange_rate, 0);
            amount = round_pr(total_khr, 100)
        }
        this.khr = amount;
        this.khr_last = khr_last;
        this.khr_name = payment_method.name;
    },
    get_khr() {
        return this.khr;
    },
    get_khr_name() {
        return this.khr_name;
    },
    is_khr() {
        return this.payment_method_id.name.includes("KHR");
    },
    export_for_printing() {
        const json = super.export_for_printing(...arguments);
        json.khr = this.khr;
        json.khr_name = this.khr_name;
        return json;
    },
});
