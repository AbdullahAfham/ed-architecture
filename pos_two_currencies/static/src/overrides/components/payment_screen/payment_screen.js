/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import {
    roundPrecision as round_pr,
} from "@web/core/utils/numbers";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { _t } from "@web/core/l10n/translation";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
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
            var lines = this.paymentLines;
            var khr_last = false;
            if((lines.length > 0) && lines[lines.length-1].name.includes("KHR")){
                khr_last=true;
            }

            if (this.pos.is_usd) {
            // if (true) {
                // Change Cash KHR payment to USD
                for (let line of this.paymentLines) {
                    if(line.is_khr()){
                        const exchange_rate = this.pos.config.exchange_rate;
                        const currency_khr = this.pos.currency_khr ? this.pos.currency_khr : this.pos.currency;
                        const amount = round_pr(line.amount/exchange_rate, 0.01);
                        // const payment_method_usd = this.pos.payment_methods.find(o => o.name.includes("USD"));
                        // this.currentOrder.remove_paymentline(line);
                        // this.currentOrder.add_paymentline(payment_method_usd);
                        // this.currentOrder.selected_paymentline.set_amount(amount);
                        // this.currentOrder.selected_paymentline.set_khr(line.payment_method,khr_last);
                        // line.set_amount(amount);
                        line.set_khr(line.payment_method, amount, khr_last);
                    }
                }
            }

            // const ticket_state = this.pos.TICKET_SCREEN_STATE;
            // let RefundName = false;
            // let ticket_order = false;
            // if (ticket_state.ui.selectedOrder) {
            //     ticket_order = ticket_state.syncedOrders.cache[ticket_state.ui.selectedOrder.backendId];
            // }
            //
            // if (ticket_state.ui.filter == "SYNCED" && ticket_state.ui.selectedOrder) {
            //     ticket_order = ticket_state.syncedOrders.cache[ticket_state.ui.selectedOrder.backendId];
            // } else {
            //     ticket_order = ticket_state.ui.selectedOrder;
            // }
            //
            // if (ticket_order){
            //     RefundName = ticket_order.order_name;
            // }
            //
            // const currentOrder = this.currentOrder;
            // const total = currentOrder.get_total_with_tax();
            //
            // if (total > 0 && RefundName) {
            //     RefundName = false;
            // }
            //
            // let sequence_name;
            // if (RefundName) {
            //     sequence_name = this.pos.order_sequence?.format ? this.currentOrder.generate_order_sequence(this.pos.order_sequence?.refund_format) : '';
            //     if (this.pos.order_sequence && this.pos.order_sequence.refund_format) {
            //         this.pos.order_sequence.refund_format.number += 1;
            //     }
            //     this.currentOrder.set_origs_order_name(ticket_order ? ticket_order.uid : RefundName);
            // } else {
            //     sequence_name = this.pos.order_sequence?.format ? this.currentOrder.generate_order_sequence(this.pos.order_sequence.format) : '';
            //     if (this.pos.order_sequence && this.pos.order_sequence.format) {
            //         this.pos.order_sequence.format.number += 1;
            //     }
            // }
            // this.currentOrder.set_order_name(sequence_name);

            await this._finalizeValidation();
        }
    },
    // Override PaymentScreen.afterOrderValidation to Apply the formatCurrencyKHR function
    // const printResult = await this.printer.print(
    //     OrderReceipt,
    //     {
    //         data: this.pos.get_order().export_for_printing(),
    //         formatCurrency: this.env.utils.formatCurrency,
    //         formatCurrencyKHR: this.pos.formatCurrencyKHR,
    //     },
    //     { webPrintFallback: true }
    // );
});
