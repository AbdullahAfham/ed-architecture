/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { patch } from "@web/core/utils/patch";

patch(TicketScreen.prototype, {
    showDisplayQueue() {
        return this.pos.config.iface_waiting_queue;
    },
    getQueueNumber(order) {
        return order.getQueueNumberDate();
    },
    //@override
    _getSearchFields() {
        return Object.assign({}, {
            SEQUENCE: {
                repr: (order) => order.order_name,
                displayName: _t("Invoice Number"),
                modelField: "name",
            },
        }, super._getSearchFields(...arguments), {
            RECEIPT_NUMBER: {
                repr: (order) => order.name,
                displayName: _t("Ref Number"),
                modelField: "pos_reference",
            },
        });
    },
});