/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ActionpadWidget } from "@point_of_sale/app/screens/product_screen/action_pad/action_pad";

patch(ActionpadWidget, {
    defaultProps: {
        ...ActionpadWidget.defaultProps,
        disabled: false,
    },
});

patch(ActionpadWidget.prototype, {
    getMainButtonClasses() {
        return "button btn d-flex flex-column flex-fill align-items-center justify-content-center fw-bolder btn-lg rounded-0"+ (this.props.disabled ? " disabled" : "");
    }
});
