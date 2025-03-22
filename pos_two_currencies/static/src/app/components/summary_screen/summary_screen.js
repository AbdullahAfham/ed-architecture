import { Dialog } from "@web/core/dialog/dialog";
import { Component, useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { SummaryDetailsReport } from "@pos_two_currencies/app/components/summary_detail_report/summary_detail_report";
import { formatCurrencyKHR } from "@pos_two_currencies/app/utils/currency";

export class SummaryScreen extends Component {
    static template = "pos_two_currencies.SummaryScreen";
    static components = { SummaryDetailsReport, Dialog };
    static props = {
        saleDetails: Object,
        close: Function,
    };
    setup() {
        this.pos = usePos();
        this.printer = useState(useService("printer"));
        this.formatCurrencyKHR = formatCurrencyKHR;
    }
    async print() {
        await this.printer.print(
            SummaryDetailsReport,
            {
                saleDetails: this.props.saleDetails,
                pos: this.pos,
                formatCurrency: this.env.utils.formatCurrency,
                formatCurrencyKHR: this.formatCurrencyKHR,
            },
            { webPrintFallback: true }
        );
    }
}
