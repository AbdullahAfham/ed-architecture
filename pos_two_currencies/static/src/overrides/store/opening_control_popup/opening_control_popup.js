/** @odoo-module */
import { OpeningControlPopup } from "@point_of_sale/app/store/opening_control_popup/opening_control_popup";
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { parseFloat } from "@web/views/fields/parsers";
import { MoneyDetailsPopup } from "@point_of_sale/app/utils/money_details_popup/money_details_popup";
import { MoneyDetailsKHRPopup } from "@pos_two_currencies/app/utils/money_details_khr_popup/money_details_khr_popup";

patch(OpeningControlPopup.prototype, {
    setup() {
        super.setup();
        this.moneyDetailsKHR = null;
        this.state = useState({
            notes: "",
            notesKHR: "",
            notesUSD: "",
            openingCash: this.pos.formatCurrencyKHR(
                this.pos.pos_session?.cash_register_balance_start || 0,
                false
            ),
            openingCashKHR: this.pos.formatCurrencyKHR(
                this.pos.pos_session?.cash_register_balance_start || 0,
                false
            ),
        });
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
    //@override
    async confirm() {
        const cashier = this.pos.get_cashier();
        this.pos.session.state = "opened";
        this.pos.data.call(
            "pos.session",
            "set_opening_control",
            [
                this.pos.session.id,
                parseFloat(this.state.openingCash),
                this.state.notes,
                parseFloat(this.state.openingCashKHR),
                this.state.notesUSD,
                this.state.notesKHR,
                cashier?.id || false,
            ],
            {},
            true
        );
        this.props.close();
    },
    async openDetailsPopup() {
        const action = _t("Cash control - opening");
        this.hardwareProxy.openCashbox(action);
        this.dialog.add(MoneyDetailsPopup, {
            moneyDetails: this.moneyDetails,
            action: action,
            getPayload: (payload) => {
                if (payload) {
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
            context: "Opening",
        });
    },
    async openDetailsKHRPopup() {
        const action = _t("Cash control - opening");
        this.hardwareProxy.openCashbox(action);
        this.dialog.add(MoneyDetailsKHRPopup, {
            moneyDetails: this.moneyDetailsKHR,
            action: action,
            getPayload: (payload) => {
                if (payload) {
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
            context: "Opening",
        });
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
