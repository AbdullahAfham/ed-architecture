/** @odoo-module */
import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { parseFloat } from "@web/views/fields/parsers";
import { MoneyDetailsKHRPopup } from "@pos_two_currencies/app/utils/money_details_khr_popup/money_details_khr_popup";
import { MoneyDetailsPopup } from "@point_of_sale/app/utils/money_details_popup/money_details_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ConnectionLostError } from "@web/core/network/rpc_service";
import {
    roundPrecision as round_pr,
} from "@web/core/utils/numbers";
import {
    deserializeDate,
    formatDateTime,
} from "@web/core/l10n/dates";

ClosePosPopup.props = [
    ...ClosePosPopup.props,
    "default_cash_details_khr",
]

patch(ClosePosPopup.prototype, {
    setup() {
        super.setup();
        this.session_name = this.pos.config?.display_name || '';
    },
    // Override Parent Method
    getInitialState() {
        const initialState = { notes: "", noteUSD: "", noteKHR: "", payments: {} };

        if (this.pos.config.cash_control) {
            initialState.payments[this.props.default_cash_details.id] = {
                // counted: "0",
                counted: this.env.utils.formatCurrency(this.props.default_cash_details.amount, false),
            };
        }
        if (this.pos.config.cash_control && this.props.default_cash_details_khr) {
            initialState.payments[this.props.default_cash_details_khr.id] = {
                // counted: "0",
                counted: this.pos.formatCurrencyKHR(this.props.default_cash_details_khr.amount, false),
            };
        }

        this.props.other_payment_methods.forEach((pm) => {
            if (pm.type === "bank") {
                initialState.payments[pm.id] = {
                    counted: this.env.utils.formatCurrency(pm.amount, false),
                };
            }
        });
        return initialState;
    },
    getDifference(paymentId) {
        const counted = this.state.payments[paymentId].counted;
        if (!this.env.utils.isValidFloat(counted)) {
            return NaN;
        }
        let payment_method = paymentId === this.props.default_cash_details?.id
                ? this.props.default_cash_details
                : this.props.other_payment_methods.find((pm) => pm.id === paymentId);
        let expectedAmount = 0.0;
        if (!payment_method) {
            payment_method = this.props.default_cash_details_khr;
            expectedAmount = round_pr(payment_method.amount, 100);
        } else {
            expectedAmount = payment_method.amount;
        }

        return parseFloat(counted) - expectedAmount;
    },
    async closeSession() {
        const cashier = this.pos.get_cashier();
        this.customerDisplay?.update({ closeUI: true });
        if (this.pos.config.cash_control) {
            const response = await this.orm.call(
                "pos.session",
                "post_closing_cash_details",
                [this.pos.pos_session.id],
                {
                    counted_cash: parseFloat(
                        this.state.payments[this.props.default_cash_details.id].counted
                    ),
                    counted_cash_khr: parseFloat(
                        this.state.payments[this.props.default_cash_details_khr.id].counted
                    ),
                    employee_id: cashier?.id || false,
                }
            );

            if (!response.successful) {
                return this.handleClosingError(response);
            }
        }

        try {
            await this.orm.call("pos.session", "update_closing_control_state_session", [
                this.pos.pos_session.id,
                this.state.notes,
                this.state.notesUSD,
                this.state.notesKHR,
            ]);
        } catch (error) {
            // We have to handle the error manually otherwise the validation check stops the script.
            // In case of "rescue session", we want to display the next popup with "handleClosingError".
            // FIXME
            if (!error.data && error.data.message !== "This session is already closed.") {
                throw error;
            }
        }

        try {
            const bankPaymentMethodDiffPairs = this.props.other_payment_methods
                .filter((pm) => pm.type == "bank")
                .map((pm) => [pm.id, this.getDifference(pm.id)]);
            const response = await this.orm.call("pos.session", "close_session_from_ui", [
                this.pos.pos_session.id,
                bankPaymentMethodDiffPairs,
            ]);
            if (!response.successful) {
                return this.handleClosingError(response);
            }
            window.location = "/web#action=point_of_sale.action_client_pos_menu";
        } catch (error) {
            if (error instanceof ConnectionLostError) {
                // Cannot redirect to backend when offline, let error handlers show the offline popup
                // FIXME POSREF: doing this means closing again when online will redo the beginning of the method
                // although it's impossible to close again because this.closeSessionClicked isn't reset to false
                // The application state is corrupted.
                throw error;
            } else {
                // FIXME POSREF: why are we catching errors here but not anywhere else in this method?
                await this.popup.add(ErrorPopup, {
                    title: _t("Closing session error"),
                    body: _t(
                        "An error has occurred when trying to close the session.\n" +
                            "You will be redirected to the back-end to manually close the session."
                    ),
                });
                window.location = "/web#action=point_of_sale.action_client_pos_menu";
            }
        }
    },
    formatKHR(value) {
        return `${round_pr(value,100)} ${this.pos.currency_khr.symbol}`;
    },
    setManualCashKHRInput(amount) {
        if (this.env.utils.isValidFloat(amount) && this.moneyDetailsKHR) {
            this.state.notes = "";
            this.moneyDetailsKHR = null;
        }
    },
    async openDetailsPopup() {
        const action = _t("Cash control - closing");
        this.hardwareProxy.openCashbox(action);
        const { confirmed, payload } = await this.popup.add(MoneyDetailsPopup, {
            moneyDetails: this.moneyDetails,
            action: action,
        });
        if (confirmed) {
            const { total, moneyDetailsNotes, moneyDetails } = payload;
            this.state.payments[this.props.default_cash_details.id].counted =
                this.env.utils.formatCurrency(total, false);
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
            this.state.payments[this.props.default_cash_details_khr.id].counted =
                this.pos.formatCurrencyKHR(total, false);
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
});