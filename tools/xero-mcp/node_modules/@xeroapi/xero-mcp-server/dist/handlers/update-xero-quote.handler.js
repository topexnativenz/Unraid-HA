import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
import { QuoteStatusCodes } from "xero-node";
import { getClientHeaders } from "../helpers/get-client-headers.js";
async function getQuote(quoteId) {
    await xeroClient.authenticate();
    // First, get the current quote to check its status
    const response = await xeroClient.accountingApi.getQuote(xeroClient.tenantId, // tenantId
    quoteId, // quoteId
    getClientHeaders());
    return response.body.quotes?.[0];
}
async function updateQuote(quoteId, lineItems, reference, terms, title, summary, quoteNumber, contactId, date, expiryDate, existingQuote) {
    // Create quote object with only the fields that are being updated
    const quote = {
        lineItems: lineItems,
        reference: reference,
        terms: terms,
        title: title,
        summary: summary,
        quoteNumber: quoteNumber,
        expiryDate: expiryDate,
    };
    // Only add contact if contactId is provided, otherwise use existing
    if (contactId) {
        quote.contact = { contactID: contactId };
    }
    else if (existingQuote?.contact) {
        quote.contact = existingQuote.contact;
    }
    // Only add date if provided, otherwise use existing
    if (date) {
        quote.date = date;
    }
    else if (existingQuote?.date) {
        quote.date = existingQuote.date;
    }
    const response = await xeroClient.accountingApi.updateQuote(xeroClient.tenantId, quoteId, // quoteId
    {
        quotes: [quote],
    }, // quotes
    undefined, // idempotencyKey
    getClientHeaders());
    return response.body.quotes?.[0];
}
/**
 * Update an existing quote in Xero
 */
export async function updateXeroQuote(quoteId, lineItems, reference, terms, title, summary, quoteNumber, contactId, date, expiryDate) {
    try {
        const existingQuote = await getQuote(quoteId);
        const quoteStatus = existingQuote?.status;
        // Only allow updates to DRAFT quotes
        if (quoteStatus !== QuoteStatusCodes.DRAFT) {
            return {
                result: null,
                isError: true,
                error: `Cannot update quote because it is not a draft. Current status: ${quoteStatus}`,
            };
        }
        const updatedQuote = await updateQuote(quoteId, lineItems, reference, terms, title, summary, quoteNumber, contactId, date, expiryDate, existingQuote);
        if (!updatedQuote) {
            throw new Error("Quote update failed.");
        }
        return {
            result: updatedQuote,
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
