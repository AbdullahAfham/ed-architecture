/** @odoo-module **/

import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreenPaymentLines.prototype, {
});

patch(PaymentScreenPaymentLines, {
    props: {
        ...PaymentScreenPaymentLines.props,
        sendPaymentStatus: { type: Function, optional: true },
    },
});
