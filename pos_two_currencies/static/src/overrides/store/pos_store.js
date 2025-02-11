/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { deserializeDate } from "@web/core/l10n/dates";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { renderToString } from "@web/core/utils/render";
import { memoize } from "@web/core/utils/functions";
import { formatMonetary } from "@web/views/fields/formatters";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";

/**
 * Gets a product image as a base64 string so that it can be sent to the
 * customer display, as the display won't be able to fetch it, since the image
 * controller requires the client to be logged. This function is memoized on the
 * product id, so that we will only do this once per product.
 *
 * @param {number} productId id of the product
 * @param {string} writeDate the write date of the product, used as a cache
 *  buster in case the product image has been changed
 * @returns {string} the base64 representation of the product's image
 */
const getProductImage = memoize(function getProductImage(productId, writeDate, isProduct = true) {
    return new Promise(function (resolve, reject) {
        const img = new Image();
        img.addEventListener("load", () => {
            const canvas = document.createElement("canvas");
            const ctx = canvas.getContext("2d");
            canvas.height = img.height;
            canvas.width = img.width;
            ctx.drawImage(img, 0, 0);
            resolve(canvas.toDataURL("image/jpeg"));
        });
        img.addEventListener("error", reject);
        if (isProduct) {
            img.src = `/web/image?model=product.product&field=image_128&id=${productId}&unique=${writeDate}`;
        } else {
            img.src = `/web/image?model=pos.queue.banner&field=image&id=${productId}&unique=${writeDate}`;
        }
    });
});

patch(PosStore.prototype, {
    /**
     * @override
     */
    async setup(env) {
        this.currency_khr = null;
        this.currency_usd = null;
        this.is_usd = true;
        await super.setup(...arguments);
    },
    cashierIsAdmin() {
        return this.get_cashier().role == "admin";
    },
    cashierHasPriceControlRights() {
        if (this.cashierIsAdmin()) {
            return true;
        } else {
            return super.cashierHasPriceControlRights();
        }
    },
    async afterProcessServerData() {
        this.currency_usd = this.data.models["res.currency"].getFirst();
        this.currency_khr = this.config.currency_khr ? this.config.currency_khr : null;
        this.is_usd = this.currency.id !== this.currency_khr?.id;
        return await super.afterProcessServerData(...arguments);
    },
    formatCurrencyKHR(value, hasSymbol = true) {
        return formatMonetary(value, {
            currencyId: this.currency_khr && this.currency_khr.id || 66,
            noSymbol: !hasSymbol,
        });
    },
    getReceiptHeaderData(order) {
        const result = super.getReceiptHeaderData(...arguments);
        result.config_name = this.config.name;
        return result;
    },
    async printReceipt({ basic = false, order = this.get_order() } = {}) {
        await this.printer.print(
            OrderReceipt,
            {
                data: this.orderExportForPrinting(order),
                formatCurrency: this.env.utils.formatCurrency,
                basic_receipt: basic,
                formatCurrencyKHR: this.pos.formatCurrencyKHR,
            },
            { webPrintFallback: true }
        );
        const nbrPrint = order.nb_print;
        await this.data.write("pos.order", [order.id], { nb_print: nbrPrint + 1 });
        return true;
    },
});
