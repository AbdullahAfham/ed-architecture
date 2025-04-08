/** @odoo-module */

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";

patch(ProductScreen.prototype, {
    getNumpadButtons() {
        const buttons = super.getNumpadButtons(...arguments);
        const priceButton = buttons.find(button => button.value === "price");
        const discountButton = buttons.find(button => button.value === "discount");
        if (discountButton) {
            discountButton.disabled = !this.pos.cashierHasPriceControlRights() || discountButton.disabled;
        }
        if (priceButton) {
            priceButton.disabled = !this.pos.cashierIsAdmin();
        }
        return buttons
    }
});
