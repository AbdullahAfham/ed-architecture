import { patch } from "@web/core/utils/patch";
import "@pos_two_currencies/overrides/store/pos_store";
import { PosStore } from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, {
});
