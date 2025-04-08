/** @odoo-module */

import { SaleDetailsButton } from "@point_of_sale/app/navbar/sale_details_button/sale_details_button";
import { patch } from "@web/core/utils/patch";
import { SummaryScreen } from "@pos_two_currencies/app/components/summary_screen/summary_screen";
import { renderToElement } from "@web/core/utils/render";

async function handleSaleDetails(pos, hardwareProxy, dialog) {
    const saleDetails = await pos.data.call(
        "report.point_of_sale.report_saledetails",
        "get_sale_details",
        [false, false, false, [pos.session.id]]
    );
    const report = renderToElement(
        "point_of_sale.SaleDetailsReport",
        Object.assign({}, saleDetails, {
            date: new Date().toLocaleString(),
            pos: pos,
            formatCurrency: pos.env.utils.formatCurrency,
        })
    );
    let result = false;
    try {
        result = await hardwareProxy.printer?.printReceipt(report);
    } finally {
        if (!result?.successful) {
            dialog.add(SummaryScreen, { saleDetails });
        }
    }
}

patch(SaleDetailsButton.prototype, {
    async onClick() {
        await handleSaleDetails(this.pos, this.hardwareProxy, this.dialog);
    },
});
