import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
import { getClientHeaders } from "../helpers/get-client-headers.js";
async function listAccounts() {
    await xeroClient.authenticate();
    const response = await xeroClient.accountingApi.getAccounts(xeroClient.tenantId, undefined, // ifModifiedSince
    undefined, // where
    undefined, // order
    getClientHeaders());
    const accounts = response.body.accounts ?? [];
    return accounts;
}
/**
 * List all accounts from Xero
 */
export async function listXeroAccounts() {
    try {
        const accounts = await listAccounts();
        return {
            result: accounts,
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
