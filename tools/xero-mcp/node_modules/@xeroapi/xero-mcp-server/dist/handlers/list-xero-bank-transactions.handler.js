import { xeroClient } from "../clients/xero-client.js";
import { getClientHeaders } from "../helpers/get-client-headers.js";
import { formatError } from "../helpers/format-error.js";
async function getBankTransactions(page, bankAccountId) {
    await xeroClient.authenticate();
    const response = await xeroClient.accountingApi.getBankTransactions(xeroClient.tenantId, undefined, // ifModifiedSince
    bankAccountId ? `BankAccount.AccountID=guid("${bankAccountId}")` : undefined, // where
    "Date DESC", // order
    page, // page
    undefined, // unitdp
    10, // pagesize
    getClientHeaders());
    return response.body.bankTransactions ?? [];
}
export async function listXeroBankTransactions(page = 1, bankAccountId) {
    try {
        const bankTransactions = await getBankTransactions(page, bankAccountId);
        return {
            result: bankTransactions,
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
