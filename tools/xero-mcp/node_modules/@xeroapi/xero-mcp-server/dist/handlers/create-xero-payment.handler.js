import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
import { getClientHeaders } from "../helpers/get-client-headers.js";
async function createPayment({ invoiceId, accountId, amount, date, reference, }) {
    await xeroClient.authenticate();
    const payment = {
        invoice: {
            invoiceID: invoiceId,
        },
        account: {
            accountID: accountId,
        },
        amount: amount,
        date: date || new Date().toISOString().split("T")[0], // Today's date if not specified
        reference: reference,
    };
    const response = await xeroClient.accountingApi.createPayment(xeroClient.tenantId, payment, undefined, // idempotencyKey
    getClientHeaders());
    return response.body.payments?.[0];
}
/**
 * Create a new payment in Xero
 */
export async function createXeroPayment({ invoiceId, accountId, amount, date, reference, }) {
    try {
        const createdPayment = await createPayment({
            invoiceId,
            accountId,
            amount,
            date,
            reference,
        });
        if (!createdPayment) {
            throw new Error("Payment creation failed.");
        }
        return {
            result: createdPayment,
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
