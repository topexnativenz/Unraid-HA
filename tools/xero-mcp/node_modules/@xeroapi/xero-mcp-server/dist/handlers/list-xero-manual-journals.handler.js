import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
import { getClientHeaders } from "../helpers/get-client-headers.js";
async function getManualJournals(page, manualJournalId, modifiedAfter) {
    await xeroClient.authenticate();
    if (manualJournalId) {
        const response = await xeroClient.accountingApi.getManualJournal(xeroClient.tenantId, manualJournalId, getClientHeaders());
        return response.body.manualJournals ?? [];
    }
    const response = await xeroClient.accountingApi.getManualJournals(xeroClient.tenantId, modifiedAfter ? new Date(modifiedAfter) : undefined, undefined, "UpdatedDateUTC DESC", page, 10, // pageSize
    getClientHeaders());
    return response.body.manualJournals ?? [];
}
/**
 * List all manual journals from Xero.
 */
export async function listXeroManualJournals(page = 1, manualJournalId, modifiedAfter) {
    try {
        const manualJournals = await getManualJournals(page, manualJournalId, modifiedAfter);
        return {
            result: manualJournals,
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
