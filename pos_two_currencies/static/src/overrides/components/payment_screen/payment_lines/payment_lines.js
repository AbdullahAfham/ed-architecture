/** @odoo-module **/

import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import { patch } from "@web/core/utils/patch";
import {
    roundDecimals as round_di,
    roundPrecision as round_pr,
    floatIsZero,
} from "@web/core/utils/numbers";

patch(PaymentScreenPaymentLines.prototype, {
    /**
     * @TODO: Remove this method when the issue is fixed.
     */
    formatLineAmount(paymentline) {
        let amount = paymentline.get_amount();
        if (paymentline.payment_method_id.name.includes("KHR")) {
            amount = round_pr(amount, 100)
            return this.pos.formatCurrencyKHR(amount);
        }
        return this.env.utils.formatCurrency(amount);
    },
});
