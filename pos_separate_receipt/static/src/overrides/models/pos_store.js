/** @odoo-module */


import { deduceUrl, random5Chars, uuidv4, getOnNotified } from "@point_of_sale/utils";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { deserializeDate } from "@web/core/l10n/dates";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { renderToString } from "@web/core/utils/render";
import { memoize } from "@web/core/utils/functions";
import { formatMonetary } from "@web/views/fields/formatters";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";

patch(PosStore.prototype, {
    getReceiptHeaderData(order) {
        const result = super.getReceiptHeaderData(...arguments);
        result.pos_khmer_name = this.config.pos_khmer_name;
        result.logo_image = this.config.logo_image;
        result.khmer_address = this.config.khmer_address;
        result.phone_number = this.config.phone_number;
        result.vat_number = this.config.vat_number;
        result.acc_holder_name = this.config.acc_holder_name;
        result.qr_image = false;
        if (this.config.qr_image){
            result.qr_image = `/web/image/pos.config/${this.config.id}/qr_image`
        }
        return result;
    },
});
