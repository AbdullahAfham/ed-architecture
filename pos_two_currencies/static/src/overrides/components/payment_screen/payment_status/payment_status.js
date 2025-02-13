/** @odoo-module */

import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { patch } from "@web/core/utils/patch";
import {
    roundDecimals as round_di,
    roundPrecision as round_pr,
    floatIsZero,
} from "@web/core/utils/numbers";
import { formatCurrencyKHR } from "@pos_two_currencies/app/utils/currency";

patch(PaymentScreenStatus.prototype, {
    get is_usd() {
      return true;
    },
    get currency() {
        return this.data.models["res.currency"].getFirst();
    },
    get currency_khr() {
        return this.data.models["res.currency"].find(currency => currency.id === 66);
    },
    get totalDueTextkhr() {
        const total = this.props.order.get_total_with_tax() + this.props.order.get_rounding_applied();
        const exchange_rate = this.props.order.config.exchange_rate;
        const total_khr = total ? round_pr(total * exchange_rate, 0) : 0;
        const khr = total ? round_pr(total_khr, 100) : 0;
        return formatCurrencyKHR(khr);
    },
    get totalDueTextUSD() {
        const total = this.props.order.get_total_with_tax() + this.props.order.get_rounding_applied();
        const exchange_rate_usd = 1;
        const khr = total ? round_pr(total*exchange_rate_usd,this.currency.rounding) : 0;
        return formatCurrencyKHR(khr);
    },
    get changeTextkhr() {
        var lines = this.props.order.payment_ids;
        var change = this.props.order.get_change();
        const exchange_rate = this.props.order.config.exchange_rate;
        if((lines.length > 0) && !lines[lines.length-1].payment_method_id.name.includes("KHR")){
            change = change - Math.floor(change/10)*10;
            this.props.order.is_khr=false;
        }
        const khr = change ? round_pr(change*exchange_rate, 100) : 0;
        return formatCurrencyKHR(khr);
    },
    get changeText() {
        var lines = this.props.order.payment_ids;
        var change = this.props.order.get_change();
        if((lines.length > 0) && lines[lines.length-1].payment_method_id.name.includes("KHR")){
            change = 0;
            this.props.order.is_khr=true;
        }
        return this.env.utils.formatCurrency(Math.floor(change/10)*10);
    },
    get remainingTextKHR() {
        const exchange_rate = this.props.order.config.exchange_rate;
        const rem_khr = this.props.order.get_due() > 0 ? round_pr(this.props.order.get_due()*exchange_rate, 100) : 0;
        return formatCurrencyKHR(rem_khr);
    },
});
