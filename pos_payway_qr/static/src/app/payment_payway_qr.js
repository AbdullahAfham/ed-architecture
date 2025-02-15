/** @odoo-module */
/* global PayWayQRAPI */

import {_t} from "@web/core/l10n/translation";
import {PaymentInterface} from "@point_of_sale/app/payment/payment_interface";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import {sprintf} from "@web/core/utils/strings";
import {
    roundPrecision as round_pr,
    floatIsZero,
} from "@web/core/utils/numbers";
import { register_payment_method } from "@point_of_sale/app/store/pos_store";

const PAYMENT_STATUS = {
    'approved': 'APPROVED',
    'declined': 'DECLINED',
    'pending': 'PENDING',
}

export class PaymentPayWayQR extends PaymentInterface {
    setup() {
        super.setup(...arguments);
        this.paymentLineResolvers = {};
    }

    send_payment_request(uuid, check_status = false) {
        super.send_payment_request(uuid);
        var order = this.pos.get_order();

        // Send Response to Customer Display
        if (!order.uiState.PaymentScreen) {
            order.uiState.PaymentScreen = {};
        }

        if (check_status && order.uiState.PaymentScreen.payWayPaymentData) {
            return this._payway_qr_check_status();
        }
        return this._payway_qr_pay(uuid);
    }

    send_payment_cancel(order, uuid) {
        super.send_payment_cancel(order, uuid);
        return this._payway_qr_cancel(order, uuid);
    }

    pending_payway_qr_line() {
        return this.pos.get_order() ? this.pos.getPendingPaymentLine("payway_qr") : null;
    }

    _call_payway_qr(data, action) {
        return this.pos.data
            .silentCall("pos.payment.method",
                action,
                [[this.payment_method_id.id], data]
            )
            .catch(this._handle_odoo_connection_failure.bind(this));
    }

    _handle_odoo_connection_failure(data = {}) {
        // handle timeout
        var line = this.pending_payway_qr_line();
        if (line) {
            line.set_payment_status("retry");
        }
        this._show_error(
            _t(
                "Could not connect to the Odoo server, please check your internet connection and try again."
            )
        );
        return Promise.reject(data); // prevent subsequent onFullFilled's from being called
    }

    _payway_qr_handle_response(response) {
        var order = this.pos.get_order();
        var line = this.pending_payway_qr_line();

        // Send Response to Customer Display
        if (!order.uiState.PaymentScreen) {
            order.uiState.PaymentScreen = {};
        }

        if (response.check_status) {
            line.set_payment_status("waitingCard");
            if (response && response.data_webhook && response.pos_session_id === order.session_id.id) {
                this.handlePayWayStatusResponse(response);
            }
            return this.waitForPayWayPaymentConfirmation();
        }

        // Save Response to Customer Display
        if (!response.cancel && response?.qrString && response?.amount) {
            order.uiState.PaymentScreen.payWayPaymentData = {
                store: this.pos.config.acc_holder_name,
                isUSD: response.amount.includes(".") || true,
                amount: response.amount,
                qrCode: response.qrString,
                qrImage: response.qrImage,
                order,
            };
            line.set_payment_status("waitingCard");
        } else {
            delete order.uiState.PaymentScreen.payWayPaymentData;
            line.set_payment_status("retry");
            if (response.status) {
                let message;
                if (response.status?.code && response.status?.message === "Duplicated Transaction ID") {
                    return this._payway_qr_check_status();
                    // message = `${response.status.message} (${response.status.code})`;
                } else {
                    message = response.status.message || _t("Payment ERROR!");
                }
                this._show_error(message);
            } else {
                this._show_error(response.status?.message || _t("Payment ERROR!"));
            }
        }
        return this.waitForPayWayPaymentConfirmation();
    }

    _payway_qr_pay(uuid) {
        var order = this.pos.get_order();

        var line = order.payment_ids.find((paymentLine) => paymentLine.uuid === uuid);
        if (line.amount < 0) {
            this._show_error(_t("Cannot process transactions with negative amount."));
            return false;
        }
        line.set_payment_status("waitingCapture");

        var data = {
            "name": order.uid,
            "pos_session_id": order.session_id.id,
            "order_lines": order.get_orderlines().map((line) => ({
                "product_name": line.get_full_product_name(),
                "quantity": line.get_quantity(),
                "price_unit": line.get_all_prices(1).priceWithTax,
                "discount": line.get_discount(),
            })),
            "total": line.amount,
        };
        
        return this._call_payway_qr(data, 'payway_qr_send_payment_request').then((res) => {
            return this._payway_qr_handle_response(res);
        });
    }

    async _payway_qr_check_status() {
        var order = this.pos.get_order();
        var data = {
            "name": order.uid,
            "pos_session_id": order.session_id.id,
        };
        return this._call_payway_qr(data, 'payway_qr_check_payment_status').then((res) => {
            return this._payway_qr_handle_response({...res, check_status: true});
        });
    }

    async _payway_qr_cancel(order) {
        if (order.uiState.PaymentScreen) {
            delete order.uiState.PaymentScreen.payWayPaymentData;
        }

        // [Dev]: We can't cancel the payment from the POS side
        // Transaction liftspan is 3 minutes
        // return this._call_payway_qr(data, 'payway_qr_send_payment_cancel').then((data) => {
        //     this._payway_qr_handle_response({...data, cancel: true});
        // });
        const resolver = this.paymentLineResolvers?.[this.pending_payway_qr_line()?.uuid];
        if (resolver) {
            resolver(false);
        }
        return true;
    }

    /**
     * This method is called from pos_bus when the payment
     * confirmation from PayWay QR API is received via the webhook and confirmed in the retrieve_session_id.
     */
    async handlePayWayStatusResponse(notification) {
        var line = this.pending_payway_qr_line();
        const order = this.pos.get_order();

        if (!notification) {
            notification = await this.pos.data.silentCall(
                "pos.payment.method",
                "get_latest_payway_qr_status",
                [[this.payment_method_id.id]]
            );
        }

        if (!notification) {
            return this._handle_odoo_connection_failure();
        }

        const transactionId = notification?.transactionId || notification?.data_webhook?.transaction_id;
        if (transactionId && order && order.uid !== transactionId) {
            return;
        }

        const isPaymentSuccessful = this.isPaymentSuccessful(notification);
        if (isPaymentSuccessful) {
            this.handleSuccessResponse(line, notification);
        } else {
            this._show_error(
                sprintf(_t("Message from PayWay QR API: %s"), notification?.data_webhook.payment_status ?? "Unknown")
            );
            line.set_payment_status("waitingCard");
        }

        // when starting to wait for the payment response we create a promise
        // that will be resolved when the payment response is received.
        // In case this resolver is lost ( for example on a refresh ) we
        // we use the handle_payment_response method on the payment line
        if (!(notification?.data_webhook && notification.data_webhook?.payment_status === PAYMENT_STATUS.pending)) {
            const resolver = this.paymentLineResolvers?.[line.uuid];
            if (resolver) {
                resolver(isPaymentSuccessful);
            } else {
                line.handle_payment_response(isPaymentSuccessful);
            }
        }
    }

    isPaymentSuccessful(notification) {
        return (
            notification && notification.data_webhook &&
            this.pending_payway_qr_line_success(notification) &&
            notification.data_webhook.payment_status === PAYMENT_STATUS.approved
        );
    }

    pending_payway_qr_line_success(notification) {
        const transactionId = notification?.transactionId || notification?.data_webhook?.transaction_id;
        const order = this.pos.get_open_orders().find(o => o.uid === transactionId);
        const line = order ? order.payment_ids.find(
            (paymentLine) =>
                paymentLine.payment_method?.use_payment_terminal === "payway_qr" &&
                !paymentLine.is_done()
        ) : null;

        if (!order || !transactionId || !line || !notification?.data_webhook) {
            return false;
        }

        const paymentAmount = parseFloat(notification.data_webhook.payment_amount) || 0;
        if (floatIsZero(line.amount - paymentAmount, this.pos.currency.decimal_places)) {
            return true;
        } else if (paymentAmount > 0 && this.payment_method_id?.payment_terminal && !order.payment_ids.filter(p => p.transaction_id === notification.data_webhook.transaction_id)?.length) {
            if (paymentAmount < line.amount) {
                const newPaymentline = this.models["pos.payment"].create({
                    pos_order_id: order,
                    payment_method_id: this.payment_method_id,
                });

                newPaymentline.set_amount(paymentAmount);
                newPaymentline.set_payment_status("done"); // Force the payment status to done
                this.handleSuccessResponse(newPaymentline, notification);
                order.payment_ids.add(newPaymentline);
            } else {
                return true;
            }
        }
        return false;
    }

    handleSuccessResponse(line, notification) {
        line.transaction_id = notification?.transactionId || notification?.data_webhook?.transaction_id;
        line.cardholder_name = notification.FullName || "";
    }

    waitForPayWayPaymentConfirmation() {
        return new Promise((resolve) => {
            this.paymentLineResolvers[this.pending_payway_qr_line()?.uuid] = resolve;
        });
    }

    _show_error (msg, title) {
        if (!title) {
            title = _t("PayWay QR API Error");
        }
        this.env.services.dialog.add(AlertDialog, {
            title: title,
            body: msg,
        });
    }

}

register_payment_method("payway_qr", PaymentPayWayQR);