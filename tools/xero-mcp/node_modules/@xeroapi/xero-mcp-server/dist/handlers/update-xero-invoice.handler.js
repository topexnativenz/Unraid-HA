import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
import { Invoice } from "xero-node";
import { getClientHeaders } from "../helpers/get-client-headers.js";
async function getInvoice(invoiceId) {
    await xeroClient.authenticate();
    // First, get the current invoice to check its status
    const response = await xeroClient.accountingApi.getInvoice(xeroClient.tenantId, invoiceId, // invoiceId
    undefined, // unitdp
    getClientHeaders());
    return response.body.invoices?.[0];
}
async function updateInvoice(invoiceId, lineItems, reference, dueDate, date, contactId) {
    const invoice = {
        lineItems: lineItems,
        reference: reference,
        dueDate: dueDate,
        date: date,
        contact: contactId ? { contactID: contactId } : undefined,
    };
    const response = await xeroClient.accountingApi.updateInvoice(xeroClient.tenantId, invoiceId, // invoiceId
    {
        invoices: [invoice],
    }, // invoices
    undefined, // unitdp
    undefined, // idempotencyKey
    getClientHeaders());
    return response.body.invoices?.[0];
}
/**
 * Update an existing invoice in Xero
 */
export async function updateXeroInvoice(invoiceId, lineItems, reference, dueDate, date, contactId) {
    try {
        const existingInvoice = await getInvoice(invoiceId);
        const invoiceStatus = existingInvoice?.status;
        // Only allow updates to DRAFT invoices
        if (invoiceStatus !== Invoice.StatusEnum.DRAFT) {
            return {
                result: null,
                isError: true,
                error: `Cannot update invoice because it is not a draft. Current status: ${invoiceStatus}`,
            };
        }
        const updatedInvoice = await updateInvoice(invoiceId, lineItems, reference, dueDate, date, contactId);
        if (!updatedInvoice) {
            throw new Error("Invoice update failed.");
        }
        return {
            result: updatedInvoice,
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
