import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
import { Invoice } from "xero-node";
import { getClientHeaders } from "../helpers/get-client-headers.js";
async function createInvoice(contactId, lineItems, type, reference, date) {
    await xeroClient.authenticate();
    const invoice = {
        type: type,
        contact: {
            contactID: contactId,
        },
        lineItems: lineItems,
        date: date || new Date().toISOString().split("T")[0], // Use provided date or today's date
        dueDate: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)
            .toISOString()
            .split("T")[0], // 30 days from now
        ...(type === Invoice.TypeEnum.ACCPAY
            ? { invoiceNumber: reference }
            : { reference: reference }),
        status: Invoice.StatusEnum.DRAFT,
    };
    const response = await xeroClient.accountingApi.createInvoices(xeroClient.tenantId, {
        invoices: [invoice],
    }, // invoices
    true, //summarizeErrors
    undefined, //unitdp
    undefined, //idempotencyKey
    getClientHeaders());
    const createdInvoice = response.body.invoices?.[0];
    return createdInvoice;
}
/**
 * Create a new invoice in Xero
 */
export async function createXeroInvoice(contactId, lineItems, type = Invoice.TypeEnum.ACCREC, reference, date) {
    try {
        const createdInvoice = await createInvoice(contactId, lineItems, type, reference, date);
        if (!createdInvoice) {
            throw new Error("Invoice creation failed.");
        }
        return {
            result: createdInvoice,
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
