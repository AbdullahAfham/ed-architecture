import { formatCurrency as webFormatCurrency } from "@web/core/currency";

export function formatCurrencyUSD(value, currency, hasSymbol = true){
    return webFormatCurrency(value, currency?.id || 1, {
        noSymbol: !hasSymbol,
    });
};

export function formatCurrencyKHR(value, currency, hasSymbol = true){
    return webFormatCurrency(value, currency?.id || 66, {
        noSymbol: !hasSymbol,
    });
};
