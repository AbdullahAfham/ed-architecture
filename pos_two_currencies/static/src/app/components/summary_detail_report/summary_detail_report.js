import { Component, useState } from "@odoo/owl";
import { omit } from "@web/core/utils/objects";

export class SummaryDetailsReport extends Component {
    static template = "pos_two_currencies.SummaryDetailsReport";
    static props = {
        pos: Object,
        saleDetails: Object,
        formatCurrency: Function,
        formatCurrencyKHR: Function,
    };
    setup() {
        this.pos = this.props.pos;
        Object.assign(this, this.props.saleDetails);
        this.formatCurrency = this.props.formatCurrency;
        this.formatCurrencyKHR = this.props.formatCurrencyKHR;
    }
}
