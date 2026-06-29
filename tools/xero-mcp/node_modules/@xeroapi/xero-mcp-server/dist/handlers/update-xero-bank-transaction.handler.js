import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
import { getClientHeaders } from "../helpers/get-client-headers.js";
import { BankTransaction } from "xero-node";
async function getBankTransaction(bankTransactionId) {
    await xeroClient.authenticate();
    const response = await xeroClient.accountingApi.getBankTransaction(xeroClient.tenantId, // xeroTenantId
    bankTransactionId, // bankTransactionID
    undefined, // unitdp
    getClientHeaders() // options
    );
    return response.body.bankTransactions?.[0];
}
async function updateBankTransaction(bankTransactionId, existingBankTransaction, type, contactId, lineItems, reference, date) {
    const bankTransaction = {
        ...existingBankTransaction,
        bankTransactionID: bankTransactionId,
        type: type ? BankTransaction.TypeEnum[type] : existingBankTransaction.type,
        contact: contactId ? { contactID: contactId } : existingBankTransaction.contact,
        lineItems: lineItems ? lineItems : existingBankTransaction.lineItems,
        reference: reference ? reference : existingBankTransaction.reference,
        date: date ? date : existingBankTransaction.date
    };
    const response = await xeroClient.accountingApi.updateBankTransaction(xeroClient.tenantId, // xeroTenantId
    bankTransactionId, // bankTransactionID
    { bankTransactions: [bankTransaction] }, // bankTransactions
    undefined, // unitdp
    undefined, // idempotencyKey
    getClientHeaders() // options
    );
    return response.body.bankTransactions?.[0];
}
export async function updateXeroBankTransaction(bankTransactionId, type, contactId, lineItems, reference, date) {
    try {
        const existingBankTransaction = await getBankTransaction(bankTransactionId);
        if (!existingBankTransaction) {
            throw new Error(`Could not find bank transaction`);
        }
        const updatedBankTransaction = await updateBankTransaction(bankTransactionId, existingBankTransaction, type, contactId, lineItems, reference, date);
        if (!updatedBankTransaction) {
            throw new Error(`Failed to update bank transaction`);
        }
        return {
            result: updatedBankTransaction,
            isError: false,
            error: null
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
