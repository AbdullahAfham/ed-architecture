/** @odoo-module */
import { PaymentMethodBreakdown } from "@point_of_sale/app/components/payment_method_breakdown/payment_method_breakdown";
import { patch } from "@web/core/utils/patch";
import { formatCurrencyKHR } from "@pos_two_currencies/app/utils/currency";

PaymentMethodBreakdown.props = {
    ...PaymentMethodBreakdown.props,
    isKHR: { type: Boolean, optional: true },
}

patch(PaymentMethodBreakdown.prototype, {
    formatCurrency(amount) {
        return this.props?.isKHR ? formatCurrencyKHR(amount) : this.env.utils.formatCurrency(amount);
    },
});