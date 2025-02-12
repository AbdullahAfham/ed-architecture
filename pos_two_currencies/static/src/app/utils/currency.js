import { formatMonetary } from "@web/views/fields/formatters";

export const formatCurrencyKHR = (value, currency, hasSymbol = true) => {
    return formatMonetary(value, {
        currencyId: currency?.id || 66,
        noSymbol: !hasSymbol,
    });
};
