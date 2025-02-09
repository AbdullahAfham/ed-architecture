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
        if (await this._isOrderValid(isForceValidate)) {
            // remove pending payments before finalizing the validation
            for (let line of this.paymentLines) {
                if (!line.is_done()){
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

            const ticket_state = this.pos.TICKET_SCREEN_STATE;
            let RefundName = false;
            let ticket_order = false;
            if (ticket_state.ui.selectedOrder) {
                ticket_order = ticket_state.syncedOrders.cache[ticket_state.ui.selectedOrder.backendId];
            }

            if (ticket_state.ui.filter == "SYNCED" && ticket_state.ui.selectedOrder) {
                ticket_order = ticket_state.syncedOrders.cache[ticket_state.ui.selectedOrder.backendId];
            } else {
                ticket_order = ticket_state.ui.selectedOrder;
            }

            if (ticket_order){
                RefundName = ticket_order.order_name;
            }

            const currentOrder = this.currentOrder;
            const total = currentOrder.get_total_with_tax();

            if (total > 0 && RefundName) {
                RefundName = false;
            }

            let sequence_name;
            if (RefundName) {
                sequence_name = this.pos.order_sequence?.format ? this.currentOrder.generate_order_sequence(this.pos.order_sequence?.refund_format) : '';
                if (this.pos.order_sequence && this.pos.order_sequence.refund_format) {
                    this.pos.order_sequence.refund_format.number += 1;
                }
                this.currentOrder.set_origs_order_name(ticket_order ? ticket_order.uid : RefundName);
            } else {
                sequence_name = this.pos.order_sequence?.format ? this.currentOrder.generate_order_sequence(this.pos.order_sequence.format) : '';
                if (this.pos.order_sequence && this.pos.order_sequence.format) {
                    this.pos.order_sequence.format.number += 1;
                }
            }

            this.currentOrder.set_order_name(sequence_name);
            await this._finalizeValidation();
       }
    },
    // Override PaymentScreen.afterOrderValidation to Apply the formatCurrencyKHR function
    async afterOrderValidation(suggestToSync = true) {
        // Remove the order from the local storage so that when we refresh the page, the order
        // won't be there
        this.pos.db.remove_unpaid_order(this.currentOrder);

        // Ask the user to sync the remaining unsynced orders.
        if (suggestToSync && this.pos.db.get_orders().length) {
            const { confirmed } = await this.popup.add(ConfirmPopup, {
                title: _t("Remaining unsynced orders"),
                body: _t("There are unsynced orders. Do you want to sync these orders?"),
            });
            if (confirmed) {
                // NOTE: Not yet sure if this should be awaited or not.
                // If awaited, some operations like changing screen
                // might not work.
                this.pos.push_orders();
            }
        }
        // Always show the next screen regardless of error since pos has to
        // continue working even offline.
        let nextScreen = this.nextScreen;

        if (
            nextScreen === "ReceiptScreen" &&
            !this.currentOrder._printed &&
            this.pos.config.iface_print_auto
        ) {
            const invoiced_finalized = this.currentOrder.is_to_invoice()
                ? this.currentOrder.finalized
                : true;

            if (invoiced_finalized) {
                const printResult = await this.printer.print(
                    OrderReceipt,
                    {
                        data: this.pos.get_order().export_for_printing(),
                        formatCurrency: this.env.utils.formatCurrency,
                        formatCurrencyKHR: this.pos.formatCurrencyKHR,
                    },
                    { webPrintFallback: true }
                );

                if (printResult && this.pos.config.iface_print_skip_screen) {
                    this.pos.removeOrder(this.currentOrder);
                    this.pos.add_new_order();
                    nextScreen = "ProductScreen";
                }
            }
        }

        this.pos.showScreen(nextScreen);
        const hasCustomerAccountAsPaymentMethod = this.currentOrder
            .get_paymentlines()
            .find((paymentline) => paymentline.payment_method.type === "pay_later");
        const partner = this.currentOrder.get_partner();
        if (hasCustomerAccountAsPaymentMethod && partner.total_due !== undefined) {
            this.pos.refreshTotalDueOfPartner(partner);
        }
    },
});
