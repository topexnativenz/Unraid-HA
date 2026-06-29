import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
import { getClientHeaders } from "../helpers/get-client-headers.js";
async function getQuotes(contactId, page, quoteNumber) {
    await xeroClient.authenticate();
    const quotes = await xeroClient.accountingApi.getQuotes(xeroClient.tenantId, undefined, // ifModifiedSince
    undefined, // dateFrom
    undefined, // dateTo
    undefined, // expiryDateFrom
    undefined, // expiryDateTo
    contactId, // contactID
    undefined, // status
    page, undefined, // order
    quoteNumber, // quoteNumber
    getClientHeaders());
    return quotes.body.quotes ?? [];
}
/**
 * List all quotes from Xero
 */
export async function listXeroQuotes(page = 1, contactId, quoteNumber) {
    try {
        const quotes = await getQuotes(contactId, page, quoteNumber);
        return {
            result: quotes,
            isError: false,
            error: null,
        };
    }
    catch (error) {
        return {
            result: null,
            isError: true,
            error: formatError(error),
        };
    }
}
