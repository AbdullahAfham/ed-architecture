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
    /**
     * @override
     */
    async setup() {
        this.currency_khr = null;
        this.currency_usd = null;
        this.is_usd = true;
        await super.setup(...arguments);
    },
    cashierIsAdmin() {
        const cashier = this.get_cashier();
        return (cashier._role == "manager") || (cashier._role == "manager");
    },
    cashierHasPriceControlRights() {
        if (this.cashierIsAdmin()) {
            return true;
        } else {
            return super.cashierHasPriceControlRights();
        }
    },
    async afterProcessServerData() {
        await super.afterProcessServerData(...arguments);
        this.currency_usd = this.data.models["res.currency"].getFirst();
        this.currency_khr = this.config.currency_khr ? this.config.currency_khr : null;
        this.is_usd = this.currency.id !== this.currency_khr?.id;
    },
    formatCurrencyKHR(value, hasSymbol = true) {
        return formatMonetary(value, {
            currencyId: this.currency_khr && this.currency_khr.id || 66,
            noSymbol: !hasSymbol,
        });
    },
    async get_order_sequence_number() {
        return await this.data.call("pos.config", "get_order_sequence_number", [this.config.id]);
    },
    async push_single_order(order) {
        order.sequence_number = await this.get_order_sequence_number();
        return super.push_single_order(...arguments);
    },
    getReceiptHeaderData(order) {
        const result = super.getReceiptHeaderData(...arguments);
        result.config_name = this.config.name;
        return result;
    },
    createNewOrder(data = {}) {
        const fiscalPosition = this.models["account.fiscal.position"].find((fp) => {
            return fp.id === this.config.default_fiscal_position_id?.id;
        });

        const uniqId = this.generate_unique_id();
        const order = this.models["pos.order"].create({
            session_id: this.session,
            company_id: this.company,
            config_id: this.config,
            picking_type_id: this.pickingType,
            user_id: this.user,
            sequence_number: this.session.sequence_number,
            access_token: uuidv4(),
            ticket_code: random5Chars(),
            fiscal_position_id: fiscalPosition,
            name: _t("Order %s", uniqId),
            pos_reference: uniqId,
            uid: uniqId,
            ...data,
        });

        this.session.sequence_number++;
        order.set_pricelist(this.config.pricelist_id);
        return order;
    },
    async printReceipt({ basic = false, order = this.get_order() } = {}) {
        await this.printer.print(
            OrderReceipt,
            {
                data: this.orderExportForPrinting(order),
                formatCurrency: this.env.utils.formatCurrency,
                basic_receipt: basic,
                formatCurrencyKHR: this.formatCurrencyKHR,
            },
            { webPrintFallback: true }
        );
        const nbrPrint = order.nb_print;
        await this.data.write("pos.order", [order.id], { nb_print: nbrPrint + 1 });
        return true;
    },
});
