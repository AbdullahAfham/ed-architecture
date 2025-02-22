/** @odoo-module */

import { Navbar } from "@point_of_sale/app/navbar/navbar";
import { patch } from "@web/core/utils/patch";

patch(Navbar.prototype, {
    // get showCashMoveButton() {
    //     const { cashier } = this.pos;
    //     return Boolean(this.pos?.config?.cash_control && this.pos?.config?.has_cash_move_permission) && (!cashier || ["manager", "admin"].includes(cashier.role));
    // },
    // get showCloseSessionButton() {
    //     return (
    //         !this.pos.config.module_pos_hr ||
    //         ["cashier", "manager", "admin"].includes(this.pos.get_cashier().role) ||
    //         this.pos.get_cashier_user_id() === this.pos.user.id
    //     );
    // },
    // get showBackendButton() {
    //     return (
    //         !this.pos.config.module_pos_hr ||
    //         (["cashier", "manager", "admin"].includes(this.pos.get_cashier().role) && this.pos.get_cashier().user_id) ||
    //         this.pos.get_cashier_user_id() === this.pos.user.id
    //     );
    // },
});
