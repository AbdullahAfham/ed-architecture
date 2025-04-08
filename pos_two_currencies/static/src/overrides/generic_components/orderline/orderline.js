/** @odoo-module */

import { Orderline } from "@point_of_sale/app/generic_components/orderline/orderline";
import { patch } from "@web/core/utils/patch";

patch(Orderline.prototype, {
});

patch(Orderline, {
    props: {
        ...Orderline.props,
        line: {
            ...Orderline.props.line,
            shape: {
                ...Orderline.props.line.shape,
                displayBorder: { type: Boolean, optional: true },
                priceNoSymbol: { type: String, optional: true },
                unitPriceNoSymbol: { type: String, optional: true },
            },
        },
    },
});