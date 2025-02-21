import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        console.log(this, "PosStore----", this.onNotified);
        this.onNotified("PAYWAY_QR_LATEST_RESPONSE", () => {
            const currentOrder = this.get_order();
            console.log("PAYWAY_QR_LATEST_RESPONSE----", currentOrder);
            if (currentOrder) {
                this.getPendingPaymentLine(
                    "payway_qr"
                ).payment_method_id.payment_terminal.handlePayWayStatusResponse();
            }
        });
    },
});
