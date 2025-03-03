/** @odoo-module */
import { CashMovePopup } from "@point_of_sale/app/navbar/cash_move_popup/cash_move_popup";
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { parseFloat } from "@web/views/fields/parsers";

patch(CashMovePopup.prototype, {
    setup() {
        super.setup();
        this.currency_khr = this.pos.currency_khr || this.pos.currency;
        this.state = useState({
            /** @type {'in'|'out'} */
            type: "out",
            amount: "",
            amountKHR: "",
            reason: "",
        });
    },

    _prepare_try_cash_in_out_payload(type, amount, reason, extras, amountKHR) {
        return [[this.pos.session.id], type, amount, reason, extras, amountKHR];
    },
    get isOnlyUSD() {
        return this.pos.config?.is_one_currency && !this.pos.config?.is_khr_currency;
    },
    get isOnlyKHR() {
        return this.pos.config?.is_one_currency && this.pos.config?.is_khr_currency;
    },
    get isBothCurrency() {
        return !this.pos.config?.is_one_currency;
    },
    async confirm() {
        const amount = parseFloat(this.state.amount);
        const amountKHR = parseFloat(this.state.amountKHR);
        const formattedAmount = this.env.utils.formatCurrency(amount);
        const formattedAmountKHR = this.pos.formatCurrencyKHR(amountKHR);
        if (!amount || !amountKHR) {
            if (!amount && !amountKHR) {
                this.notification.add(_t("Cash in/out of %s is ignored.", formattedAmount), 3000);
            }
            // if (!amountKHR) {
            //     this.notification.add(_t("Cash in/out of %s is ignored.", formattedAmountKHR), 3000);
            // }
            if (!amount && !amountKHR) {
                return this.props.close();
            }
        }

        const type = this.state.type;
        const translatedType = _t(type);
        const extras = { formattedAmount, formattedAmountKHR, translatedType };
        const reason = this.state.reason.trim();
        await this.pos.data.call(
            "pos.session",
            "try_cash_in_out",
            this._prepare_try_cash_in_out_payload(type, amount, reason, extras, amountKHR),
            {},
            true
        );

        if (amount) {
            await this.pos.logEmployeeMessage(
                `${_t("Cash")} ${translatedType} - ${_t("Amount (USD)")}: ${formattedAmount}`,
                "CASH_DRAWER_ACTION"
            );
        }
        if (amountKHR) {
            await this.pos.logEmployeeMessage(
                `${_t("Cash")} ${translatedType} - ${_t("Amount (KHR)")}: ${formattedAmountKHR}`,
                "CASH_DRAWER_ACTION"
            );
        }

        // Dev: Remove print cashout receipt
        // await this.printer.print(CashMoveReceipt, {
        //     reason,
        //     translatedType,
        //     formattedAmount,
        //     headerData: this.pos.getReceiptHeaderData(),
        //     date: new Date().toLocaleString(),
        // });

        this.props.close();
        if (amount) {
            this.notification.add(
                _t("Successfully made a cash %s of %s.", type, formattedAmount),
                3000
            );
        }
        if (amountKHR) {
            this.notification.add(
                _t("Successfully made a cash %s of %s.", type, formattedAmountKHR),
                3000
            );
        }
    }
});