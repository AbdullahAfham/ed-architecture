/** @odoo-module **/
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(ControlButtons.prototype, {
    clickDiscountAll() {
        let discount_all = this.currentOrder?.get_discount_all() || 0;
        this.dialog.add(NumberPopup, {
            startingValue: discount_all,
            title: _t("Discount All (Percentage)"),
            getPayload: (inputNumber) => {
                const discountAmount = Math.max(0, Math.min(100, parseFloat(inputNumber, 10)));
                this.currentOrder.set_discount_all(discountAmount)
                this.currentOrder.get_orderlines().forEach(function (orderline) {
                    orderline.set_discount(discountAmount)
                });
            },
        });
    },
    // TODO: Check apply_discount
    async apply_discount(pc) {
        const order = this.pos.get_order();
        const lines = order.get_orderlines();
        const product = this.pos.config.discount_product_id;

        if (product === undefined) {
            this.dialog.add(AlertDialog, {
                title: _t("No discount product found"),
                body: _t(
                    "The discount product seems misconfigured. Make sure it is flagged as 'Can be Sold' and 'Available in Point of Sale'."
                ),
            });
            return;
        }
        // Remove existing discounts
        lines.filter((line) => line.get_product() === product).forEach((line) => line.delete());

        // Add one discount line per tax group
        const linesByTax = order.get_orderlines_grouped_by_tax_ids();
        for (const [tax_ids, lines] of Object.entries(linesByTax)) {
            // Note that tax_ids_array is an Array of tax_ids that apply to these lines
            // That is, the use case of products with more than one tax is supported.
            const tax_ids_array = tax_ids
                .split(",")
                .filter((id) => id !== "")
                .map((id) => Number(id));

            const baseToDiscount = order.calculate_base_amount(
                lines.filter((ll) => ll.isGlobalDiscountApplicable())
            );

            let taxes = tax_ids_array
                .map((taxId) => this.pos.models["account.tax"].get(taxId))
                .filter(Boolean);

            // [DEV] Custom for disable discount TAX
            let is_discount_vat = false;
            for (let i = 0; i < taxes.length; i++) {
                if (taxes[i].is_discount_vat === true) {
                    is_discount_vat = true;
                    break;
                }
            }
            if (!is_discount_vat) {
                taxes = []
            }
            // END Custom

            // We add the price as manually set to avoid recomputation when changing customer.
            const discount = (-pc / 100.0) * baseToDiscount;
            if (discount < 0) {
                await this.pos.addLineToCurrentOrder(
                    { product_id: product, price_unit: discount, tax_ids: [["link", ...taxes]] },
                    { merge: false }
                );
            }
        }
    },
});
