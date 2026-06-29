import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
import { getClientHeaders } from "../helpers/get-client-headers.js";
async function getPayments(page = 1, { invoiceNumber, invoiceId, paymentId, reference, }) {
    await xeroClient.authenticate();
    // Build where clause for filtering
    const whereConditions = [];
    if (invoiceId) {
        whereConditions.push(`Invoice.InvoiceID==guid("${invoiceId}")`);
    }
    if (invoiceNumber) {
        whereConditions.push(`Invoice.InvoiceNumber=="${invoiceNumber}"`);
    }
    if (paymentId) {
        whereConditions.push(`PaymentID==guid("${paymentId}")`);
    }
    if (reference) {
        whereConditions.push(`Reference=="${reference}"`);
    }
    // Combine conditions
    const where = whereConditions.length > 0 ? whereConditions.join(" AND ") : undefined;
    const response = await xeroClient.accountingApi.getPayments(xeroClient.tenantId, undefined, // ifModifiedSince
    where, "UpdatedDateUTC DESC", // order
    page, // page
    10, // pageSize
    getClientHeaders());
    return response.body.payments ?? [];
}
/**
 * List payments from Xero
 */
export async function listXeroPayments(page = 1, { invoiceNumber, invoiceId, paymentId, reference, }) {
    try {
        const payments = await getPayments(page, {
            invoiceNumber,
            invoiceId,
            paymentId,
            reference,
        });
        return {
            result: payments,
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
