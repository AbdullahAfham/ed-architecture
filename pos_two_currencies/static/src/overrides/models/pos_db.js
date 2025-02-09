/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosDB } from "@point_of_sale/app/store/db";

patch(PosDB.prototype, {
    /**
     * Return the orders with requested ids if they are unpaid.
     * @param {array<number>} ids order_ids.
     * @return {array<object>} list of orders.
     */
    get_unpaid_orders_to_sync: function(ids){
        var saved = this.load('unpaid_orders',[]);
        var orders = [];
        saved.forEach(function(o) {
            if (ids.includes(o.id) && (o.data.server_id || o.data.lines.length)){
                orders.push(o);
            }
        });
        return orders;
    },
});
