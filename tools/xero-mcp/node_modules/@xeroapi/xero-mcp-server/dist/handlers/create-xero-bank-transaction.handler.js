import { xeroClient } from "../clients/xero-client.js";
import { BankTransaction } from "xero-node";
import { formatError } from "../helpers/format-error.js";
import { getClientHeaders } from "../helpers/get-client-headers.js";
async function createBankTransaction(type, bankAccountId, contactId, lineItems, reference, date) {
    await xeroClient.authenticate();
    const bankTransaction = {
        type: BankTransaction.TypeEnum[type],
        bankAccount: {
            accountID: bankAccountId
        },
        contact: {
            contactID: contactId
        },
        lineItems: lineItems,
        date: date ?? new Date().toISOString().split("T")[0],
        reference: reference,
        status: BankTransaction.StatusEnum.AUTHORISED
    };
    const response = await xeroClient.accountingApi.createBankTransactions(xeroClient.tenantId, // xeroTenantId
    {
        bankTransactions: [bankTransaction]
    }, // bankTransactions
    true, // summarizeErrors
    undefined, // unitdp
    undefined, // idempotencyKey
    getClientHeaders());
    const createdBankTransaction = response.body.bankTransactions?.[0];
    return createdBankTransaction;
}
export async function createXeroBankTransaction(type, bankAccountId, contactId, lineItems, reference, date) {
    try {
        const createdTransaction = await createBankTransaction(type, bankAccountId, contactId, lineItems, reference, date);
        if (!createdTransaction) {
            throw new Error("Bank transaction creation failed.");
        }
        return {
            result: createdTransaction,
            isError: false,
            error: null
        };
    }
    catch (error) {
        return {
            result: null,
            isError: true,
            error: formatError(error)
        };
    }
}
