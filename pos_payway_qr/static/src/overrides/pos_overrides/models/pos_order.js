import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { formatCurrencyKHR, formatCurrencyUSD } from "@pos_two_currencies/app/utils/currency";

patch(PosOrder.prototype, {
    getCustomerDisplayData() {
        const changeKHR = this.changeTextkhr();
        const changeUSD = this.changeText();
        return {
            ...super.getCustomerDisplayData(),
            payWayPaymentData: { ...this.payWayPaymentData },
            changeUSD: changeUSD && formatCurrencyUSD(changeUSD),
            changeKHR: changeKHR && formatCurrencyKHR(changeKHR),
            amount: formatCurrencyUSD(this.get_total_with_tax() || 0),
            amountKHR: formatCurrencyKHR(this.get_total_khr() || 0),
            paymentLines: this.payment_ids.map((pl) => ({
                name: pl.payment_method_id.name,
                amount: pl.is_khr() ? formatCurrencyKHR(pl.get_amount()) : formatCurrencyUSD(pl.get_amount()),
            })),
        };
    },
});
