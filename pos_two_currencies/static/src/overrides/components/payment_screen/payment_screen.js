/** @odoo-module */
import { AlertDialog, ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import {
    roundPrecision as round_pr,
} from "@web/core/utils/numbers";
import { formatCurrencyKHR } from "@pos_two_currencies/app/utils/currency";
import { _t } from "@web/core/l10n/translation";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
    },
    get totalDueTextkhr() {
        const total = this.currentOrder.get_total_with_tax() + this.currentOrder.get_rounding_applied();
        const exchange_rate = this.currentOrder.config.exchange_rate;
        const total_khr = total ? round_pr(total * exchange_rate, 0) : 0;
        const khr = total ? round_pr(total_khr, 100) : 0;
        return formatCurrencyKHR(khr);
    },
    get totalDueTextUSD() {
        const total = this.currentOrder.get_total_with_tax() + this.currentOrder.get_rounding_applied();
        const exchange_rate_usd = 1;
        const khr = total ? round_pr(total*exchange_rate_usd,this.currency.rounding) : 0;
        return formatCurrencyKHR(khr);
    },
    async validateOrder(isForceValidate) {
        this.numberBuffer.capture();
        if (this.pos.config.cash_rounding) {
            if (!this.currentOrder.check_paymentlines_rounding()) {
                this._display_popup_error_paymentlines_rounding();
                return;
            }
        }
        if (await this._isOrderValid(isForceValidate)) {
            // remove pending payments before finalizing the validation
            for (const line of this.paymentLines) {
                if (!line.is_done()) {
                    this.currentOrder.remove_paymentline(line);
                }
            }

            // Update Payment line status
            const lines = this.paymentLines;
            let khr_last = false;
            if((lines.length > 0) && lines[lines.length-1].payment_method_id.name.includes("KHR")){
                khr_last=true;
            }

            // Change Cash KHR payment to USD
            for (let line of this.paymentLines) {
                if(line.is_khr()){
                    const exchange_rate = this.pos.config.exchange_rate;
                    line.amount = line.amount / exchange_rate; // Convert KHR to USD
                    line.set_khr(line.payment_method_id, line.amount, khr_last);
                }
            }

            try {
                this.currentOrder.name  = await this.pos.get_order_sequence_number();
            } catch (error) {
                this.dialog.add(AlertDialog, {
                    title: _t("Cannot Get Order Sequence Number"),
                    body: _t("Please make sure you are connected to the network."),
                });
            }

            await this._finalizeValidation();
        }
    },
});
