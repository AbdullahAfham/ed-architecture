/** @odoo-module */

import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { formatDateTime } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { OfflineErrorPopup } from "@point_of_sale/app/errors/popups/offline_error_popup";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { onMounted } from "@odoo/owl";

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup(...arguments);
        if (!this.currentOrder?._printed) {
            onMounted(this.printReceipt);
        }
    },
    get khr_rate() {
        return this.receiptEnv.order.pos.config.exchange_rate;
    },
    // Dev: For POS restaurant
    get table() {
        return this.props.order.getTable()?.name;
    },
    get date() {
        const now = luxon.DateTime.now();
        const date = this.date_order ? this.date_order.plus({ hours: 7 }) : now;
        if (date > now) {
            date.minus({ hours: 7 })
        }
        return formatDateTime(date, { format: 'dd-MM-yyyy hh:mm a' });
    },
    async printReceipt() {
        this.buttonPrintReceipt.el.className = "fa fa-fw fa-spin fa-circle-o-notch";
        const isPrinted = await this.printer.print(
            OrderReceipt,
            {
                data: this.pos.get_order().export_for_printing(),
                formatCurrency: this.env.utils.formatCurrency,
                formatCurrencyKHR: this.pos.formatCurrencyKHR,
            },
            { webPrintFallback: true }
        );

        if (isPrinted) {
            this.currentOrder._printed = true;
        }

        if (this.buttonPrintReceipt.el) {
            this.buttonPrintReceipt.el.className = "fa fa-print";
        }
    },
    async sendToCustomer(orderPartner, methodName) {
        const ticketImage = await this.renderer.toJpeg(
            OrderReceipt,
            {
                data: this.pos.get_order().export_for_printing(),
                formatCurrency: this.env.utils.formatCurrency,
                formatCurrencyKHR: this.pos.formatCurrencyKHR,
            },
            { addClass: "pos-receipt-print" }
        );
        const order = this.currentOrder;
        const orderName = order.get_name();
        const order_server_id = this.pos.validated_orders_name_server_id_map[orderName];
        if (!order_server_id) {
            this.popup.add(OfflineErrorPopup, {
                title: _t("Unsynced order"),
                body: _t(
                    "This order is not yet synced to server. Make sure it is synced then try again."
                ),
            });
            return Promise.reject();
        }
        await this.orm.call("pos.order", methodName, [
            [order_server_id],
            orderName,
            orderPartner,
            ticketImage,
        ]);
    }
});
