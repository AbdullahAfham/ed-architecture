/** @odoo-module */
import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { parseFloat } from "@web/views/fields/parsers";
import { MoneyDetailsKHRPopup } from "@pos_two_currencies/app/utils/money_details_khr_popup/money_details_khr_popup";
import { MoneyDetailsPopup } from "@point_of_sale/app/utils/money_details_popup/money_details_popup";
import {
    roundPrecision as round_pr,
} from "@web/core/utils/numbers";
import { ConnectionLostError } from "@web/core/network/rpc";
import { deduceUrl } from "@point_of_sale/utils";

ClosePosPopup.props = [
    ...ClosePosPopup.props,
    "default_cash_details_khr",
]

patch(ClosePosPopup.prototype, {
    setup() {
        super.setup();
        this.session_name = this.pos.config?.display_name || '';
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
    // Override Parent Method
    getInitialState() {
        const initialState = { notes: "", noteUSD: "", noteKHR: "", payments: {} };

        if (this.pos.config.cash_control && this.props.default_cash_details) {
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

        this.props.non_cash_payment_methods.forEach((pm) => {
            if (pm.type === "bank") {
                initialState.payments[pm.id] = {
                    counted: this.env.utils.formatCurrency(pm.amount, false),
                };
            }
        });
        return initialState;
    },
    get cashKHRMoveData() {
        const { total, moves } = this.props.default_cash_details_khr.moves.reduce(
            (acc, move, i) => {
                acc.total += move.amount;
                acc.moves.push({
                    id: i,
                    name: move.name,
                    amount: move.amount,
                });
                return acc;
            },
            { total: 0, moves: [] }
        );
        return { total, moves };
    },

    getDifference(paymentId) {
        const counted = this.state.payments[paymentId].counted;
        if (!this.env.utils.isValidFloat(counted)) {
            return NaN;
        }
        let payment_method = paymentId === this.props.default_cash_details?.id
                ? this.props.default_cash_details
                : this.props.non_cash_payment_methods.find((pm) => pm.id === paymentId);
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
        this.pos._resetConnectedCashier();
        if (this.pos.config.customer_display_type === "proxy") {
            const proxyIP = this.pos.getDisplayDeviceIP();
            fetch(`${deduceUrl(proxyIP)}/hw_proxy/customer_facing_display`, {
                method: "POST",
                headers: {
                    Accept: "application/json",
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ params: { action: "close" } }),
            }).catch(() => {
                console.log("Failed to send data to customer display");
            });
        }
        // If there are orders in the db left unsynced, we try to sync.
        const syncSuccess = await this.pos.push_orders_with_closing_popup();
        if (!syncSuccess) {
            return;
        }
        if (this.pos.config.cash_control) {
            const cashier = this.pos.get_cashier();
            const response = await this.pos.data.call(
                "pos.session",
                "post_closing_cash_details",
                [this.pos.session.id],
                {
                    counted_cash: this.props.default_cash_details ? parseFloat(
                        this.state.payments[this.props.default_cash_details.id].counted
                    ) : 0,
                    counted_cash_khr: this.props.default_cash_details_khr ? parseFloat(
                        this.state.payments[this.props.default_cash_details_khr.id].counted
                    ) : 0,
                    user_id: cashier?.id || false,

                }
            );

            if (!response.successful) {
                return this.handleClosingError(response);
            }
        }

        try {
            await this.pos.data.call("pos.session", "update_closing_control_state_session", [
                this.pos.session.id,
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
            const bankPaymentMethodDiffPairs = this.props.non_cash_payment_methods
                .filter((pm) => pm.type == "bank")
                .map((pm) => [pm.id, this.getDifference(pm.id)]);
            const response = await this.pos.data.call(
                "pos.session",
                "close_session_from_ui",
                [this.pos.session.id, bankPaymentMethodDiffPairs],
                {
                    context: {
                        login_number: odoo.login_number,
                    },
                }
            );
            if (!response.successful) {
                return this.handleClosingError(response);
            }
            localStorage.removeItem(`pos.session.${odoo.pos_config_id}`);
            location.reload();
        } catch (error) {
            if (error instanceof ConnectionLostError) {
                throw error;
            } else {
                await this.handleClosingControlError();
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
    autoFillCashKHRCount() {
        const count = this.props.default_cash_details_khr.amount;
        this.state.payments[this.props.default_cash_details_khr.id].counted =
            this.pos.formatCurrencyKHR(count, false)
        this.setManualCashKHRInput(count);
    },
    async openDetailsPopup() {
        const action = _t("Cash control - closing");
        this.hardwareProxy.openCashbox(action);
        this.dialog.add(MoneyDetailsPopup, {
            moneyDetails: this.moneyDetails,
            action: action,
            getPayload: (payload) => {
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
            },
            context: "Closing",
        });
    },
    async openDetailsKHRPopup() {
        const action = _t("Cash control - closing");
        this.hardwareProxy.openCashbox(action);
        this.dialog.add(MoneyDetailsKHRPopup, {
            moneyDetails: this.moneyDetailsKHR,
            action: action,
            getPayload: (payload) => {
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
            },
            context: "Closing",
        });
    },
});