/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { onMounted } from "@odoo/owl";
import { floatIsZero } from "@web/core/utils/numbers";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => {
            const pendingPaymentLine = this.currentOrder.payment_ids.find(
                (paymentLine) =>
                    paymentLine.payment_method_id.use_payment_terminal === "payway_qr" &&
                    !paymentLine.is_done() &&
                    paymentLine.get_payment_status() !== "pending"
            );
            if (pendingPaymentLine && !this.currentOrder.uiState?.PaymentScreen?.payWayPaymentData) {
                pendingPaymentLine.set_payment_status('retry');
            }
        });
    },

    deletePaymentLine(uuid) {
        const line = this.paymentLines.find((line) => line.uuid === uuid);
        if (this.pos.paymentTerminalInProgress && line.payment_method_id.use_payment_terminal === "payway_qr") {
            this.pos.paymentTerminalInProgress = false;
        }
        super.deletePaymentLine(uuid);
    },
    async sendPaymentStatus(line) {
        // Other payment lines can not be reversed anymore
        this.numberBuffer.capture();
        this.paymentLines.forEach(function (line) {
            line.can_be_reversed = false;
        });

        line.set_payment_status("waiting");
        const isPaymentSuccessful = await line.handle_payment_response(
            await line.payment_method_id.payment_terminal.send_payment_request(line.uid, true)
        );
        // Automatically validate the order when after an electronic payment,
        // the current order is fully paid and due is zero.
        const { config, currency } = this.pos;
        const currentOrder = this.pos.get_order();
        if (
            isPaymentSuccessful &&
            currentOrder.is_paid() &&
            floatIsZero(currentOrder.get_due(), currency.decimal_places) &&
            config.auto_validate_terminal_payment
        ) {
            this.validateOrder(false);
        }
    }
});
