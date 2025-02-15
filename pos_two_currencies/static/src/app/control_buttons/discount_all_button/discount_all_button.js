/** @odoo-module **/
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(ControlButtons.prototype, {
    clickDiscountAll() {
        let discount_all = this.currentOrder?.get_discount_all() || 0;
        this.dialog.add(NumberPopup, {
            startingValue: discount_all,
            title: _t("Discount All (Percentage)"),
            getPayload: (inputNumber) => {
                const discountAmount = Math.max(0, Math.min(100, parseFloat(inputNumber, 10)));
                this.currentOrder.set_discount_all(discountAmount)
                this.currentOrder.get_orderlines().forEach(function (orderline) {
                    orderline.set_discount(discountAmount)
                });
            },
        });
    },
});
