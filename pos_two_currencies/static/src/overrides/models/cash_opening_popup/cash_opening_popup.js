/** @odoo-module */

import { CashOpeningPopup } from "@point_of_sale/app/store/cash_opening_popup/cash_opening_popup";
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { parseFloat } from "@web/views/fields/parsers";
import { MoneyDetailsKHRPopup } from "@pos_two_currencies/app/utils/money_details_khr_popup/money_details_khr_popup";
import { MoneyDetailsPopup } from "@point_of_sale/app/utils/money_details_popup/money_details_popup";

patch(CashOpeningPopup.prototype, {
    setup() {
        super.setup();
        this.moneyDetailsKHR = null;
        this.state = useState({
            notes: "",
            notesKHR: "",
            notesUSD: "",
            openingCash: this.pos.formatCurrencyKHR(
                this.pos.pos_session.cash_register_balance_start || 0,
                false
            ),
            openingCashKHR: this.pos.formatCurrencyKHR(
                this.pos.pos_session.cash_register_balance_start_khr || 0,
                false
            ),
        });
    },
    //@override
    async confirm() {
        const cashier = this.pos.get_cashier();
        this.pos.pos_session.state = "opened";
        this.orm.call("pos.session", "set_cashbox_pos", [
            this.pos.pos_session.id,
            parseFloat(this.state.openingCash),
            this.state.notes,
            parseFloat(this.state.openingCashKHR),
            this.state.notesUSD,
            this.state.notesKHR,
            cashier?.id || false,
        ]);
        this.props.close({ confirmed: true, payload: await this.getPayload() });
    },
    async openDetailsPopup() {
        const action = _t("Cash control - opening");
        this.hardwareProxy.openCashbox(action);
        const { confirmed, payload } = await this.popup.add(MoneyDetailsPopup, {
            moneyDetails: this.moneyDetails,
            action: action,
        });
        if (confirmed) {
            const { total, moneyDetails, moneyDetailsNotes } = payload;
            this.state.openingCash = this.pos.formatCurrencyKHR(total, false);
            if (moneyDetailsNotes) {
                this.state.noteUSD = moneyDetailsNotes;
                if (this.state.noteKHR) {
                    this.state.notes = `${moneyDetailsNotes}\n${this.state.noteKHR}`;
                } else {
                    this.state.notes = moneyDetailsNotes;
                }
            }
            this.moneyDetails = moneyDetails;
        }
    },
    async openDetailsKHRPopup() {
        const action = _t("Cash control - opening");
        this.hardwareProxy.openCashbox(action);
        const { confirmed, payload } = await this.popup.add(MoneyDetailsKHRPopup, {
            moneyDetails: this.moneyDetailsKHR,
            action: action,
        });
        if (confirmed) {
            const { total, moneyDetails, moneyDetailsNotes } = payload;
            this.state.openingCashKHR = this.pos.formatCurrencyKHR(total, false);
            if (moneyDetailsNotes) {
                this.state.noteKHR = moneyDetailsNotes;
                if (this.state.noteUSD) {
                    this.state.notes = `${this.state.noteUSD}\n${moneyDetailsNotes}`;
                } else {
                    this.state.notes = moneyDetailsNotes;
                }
            }
            this.moneyDetailsKHR = moneyDetails;
        }
    },
    handleInputChange() {
        if (!this.env.utils.isValidFloat(this.state.openingCash)) {
            return;
        }
        if (this.state.noteKHR) {
            this.state.notes = this.state.noteKHR;
        } else {
            this.state.notes = "";
        }
    },
    handleInputChangeKHR() {
        if (!this.env.utils.isValidFloat(this.state.openingCashKHR)) {
            return;
        }
        if (this.state.noteUSD) {
            this.state.notes = this.state.noteUSD;
        } else {
            this.state.notes = "";
        }
    }
});
