/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { floatIsZero } from "@web/core/utils/numbers";
import { NumericInput } from "@point_of_sale/app/generic_components/inputs/numeric_input/numeric_input";

export class MoneyDetailsKHRPopup extends AbstractAwaitablePopup {
    static template = "pos_two_currencies.MoneyDetailsKHRPopup";
    static components = { NumericInput };

    setup() {
        super.setup();
        this.pos = usePos();
        this.bills = [
            {id: 1, name: '50', value: 50},
            {id: 2, name: '100', value: 100},
            {id: 3, name: '200', value: 200},
            {id: 4, name: '500', value: 500},
            {id: 5, name: '1000', value: 1000},
            {id: 6, name: '2000', value: 2000},
            {id: 7, name: '5000', value: 5000},
            {id: 8, name: '10000', value: 10000},
            {id: 9, name: '15000', value: 15000},
            {id: 10, name: '20000', value: 20000},
            {id: 11, name: '30000', value: 30000},
            {id: 12, name: '50000', value: 50000},
            {id: 13, name: '100000', value: 100000},
            {id: 14, name: '200000', value: 200000},
        ];
        this.currency = this.pos.currency_khr || this.pos.currency;
        this.state = useState({
            moneyDetails: this.props.moneyDetails
                ? { ...this.props.moneyDetails }
                : Object.fromEntries(this.bills.map((bill) => [bill.value, 0])),
        });
    }
    computeTotal(moneyDetails = this.state.moneyDetails) {
        return Object.entries(moneyDetails).reduce(
            (total, money) => total + money[0] * money[1],
            0
        );
    }
    //@override
    async getPayload() {
        let moneyDetailsNotes = !floatIsZero(this.computeTotal(), this.currency.decimal_places)
            ? "Money details (KHR): \n"
            : null;
        this.bills.forEach((bill) => {
            if (this.state.moneyDetails[bill.value]) {
                moneyDetailsNotes += `  - ${
                    this.state.moneyDetails[bill.value]
                } x ${this.pos.formatCurrencyKHR(bill.value)}\n`;
            }
        });
        return {
            total: this.computeTotal(),
            moneyDetailsNotes,
            moneyDetails: { ...this.state.moneyDetails },
            action: this.props.action,
        };
    }
    async cancel() {
        super.cancel();
        if (
            this.pos.config.iface_cashdrawer &&
            this.pos.hardwareProxy.connectionInfo.status === "connected"
        ) {
            this.pos.logEmployeeMessage(this.props.action, "ACTION_CANCELLED");
        }
    }
    _parseFloat(value) {
        return parseFloat(value);
    }
}
