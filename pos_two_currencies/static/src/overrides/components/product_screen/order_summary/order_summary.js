import { patch } from "@web/core/utils/patch";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { formatDateTime } from "@web/core/l10n/dates";

patch(OrderSummary.prototype, {
    get date() {
        return formatDateTime(luxon.DateTime.now(), { format: 'dd-MM-yyyy hh:mm a' });
    },
    get totalKHR() {
        return this.currentOrder && !this.env.utils.floatIsZero(this.currentOrder.get_total_khr()) && this.currentOrder.getKHR() || ''
    }
});
