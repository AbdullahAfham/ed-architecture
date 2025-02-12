import { formatCurrency as webFormatCurrency } from "@web/core/currency";

export const formatCurrencyKHR = (value, currency, hasSymbol = true) => {
        return webFormatCurrency(value, currency?.id || 66, {
            noSymbol: !hasSymbol,
        });
};
