/** @odoo-module */

import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { formatDateTime } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { onMounted } from "@odoo/owl";

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup(...arguments);
        if (!this.currentOrder?.nb_print < 1) {
            onMounted(() => this.pos.printReceipt());
        }
    },
    get khr_rate() {
        return this.pos.config.exchange_rate;
    },
    get date() {
        const now = luxon.DateTime.now();
        const date = this.date_order ? this.date_order.plus({ hours: 7 }) : now;
        if (date > now) {
            date.minus({ hours: 7 })
        }
        return formatDateTime(date, { format: 'dd-MM-yyyy hh:mm a' });
    },
    async generateTicketImage(isBasicReceipt = false) {
        await this.renderer.toJpeg(
            OrderReceipt,
            {
                data: this.pos.orderExportForPrinting(this.pos.get_order()),
                formatCurrency: this.env.utils.formatCurrency,
                basic_receipt: isBasicReceipt,
                formatCurrencyKHR: this.pos.formatCurrencyKHR,
            },
            { addClass: "pos-receipt-print p-3" }
        );
    },
});
