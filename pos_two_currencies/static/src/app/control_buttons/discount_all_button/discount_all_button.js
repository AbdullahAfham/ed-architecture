/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";

export class DiscountButton extends Component {
    static template = "pos_two_currencies.DiscountAllButton";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
    }
    get selectedOrderline() {
        return this.pos.get_order().get_selected_orderline();
    }
    disableButton() {
        return this.selectedOrderline;
    }
    async click() {
        if (!this.selectedOrderline) {
            return;
        }

        var self = this;
        var order = self.pos.get_order();
        var discount_all = order.get_discount_all();

        const { confirmed, payload } = await this.popup.add(NumberPopup, {
            title: _t("Discount All (Percentage)"),
            startingValue: discount_all ? discount_all : null,
            isInputSelected: true,
        });
        if (confirmed) {
            const val = Math.max(0, Math.min(100, parseFloat(payload)));
            order.set_discount_all(val)
            order.get_orderlines().forEach(function (orderline) {
                orderline.set_discount(val)
            });
        }
    }
}
