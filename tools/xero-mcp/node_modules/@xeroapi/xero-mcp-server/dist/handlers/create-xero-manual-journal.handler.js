import { xeroClient } from "../clients/xero-client.js";
import { getClientHeaders } from "../helpers/get-client-headers.js";
import { formatError } from "../helpers/format-error.js";
async function createManualJournal(narration, manualJournalLines, date, lineAmountTypes, status, url, showOnCashBasisReports) {
    await xeroClient.authenticate();
    const manualJournal = {
        narration,
        journalLines: manualJournalLines.map((journalLine) => ({
            lineAmount: journalLine.lineAmount,
            accountCode: journalLine.accountCode,
            description: journalLine.description,
            taxType: journalLine.taxType,
            // TODO: tracking can be added here
        })),
        date: date,
        lineAmountTypes: lineAmountTypes,
        status: status,
        url: url,
        showOnCashBasisReports: showOnCashBasisReports,
    };
    const manualJournals = {
        manualJournals: [manualJournal],
    };
    const response = await xeroClient.accountingApi.createManualJournals(xeroClient.tenantId, manualJournals, true, undefined, getClientHeaders());
    return response.body.manualJournals?.[0];
}
/**
 * Create a manual journal in Xero.
 * @param narration - Required: Description of manual journal being posted.
 * @param manualJournalLines - Required: Array of `ManualJournalLine` objects.
 * @param date - Optional: YYYY-MM-DD format.
 * @param lineAmountTypes - Optional: No Tax by default, see `ManualJournal.LineAmountTypesEnum`.
 * @param status - Optional: draft by default, see `ManualJournal.StatusEnum`.
 * @param url - Optional: URL link to a source document.
 * @param showOnCashBasisReports - Optional: default is true if not specified.
 * @returns
 */
export async function createXeroManualJournal(narration, manualJournalLines, date, lineAmountTypes, status, url, showOnCashBasisReports) {
    try {
        const createdManualJournal = await createManualJournal(narration, manualJournalLines, date, lineAmountTypes, status, url, showOnCashBasisReports);
        if (!createdManualJournal) {
            throw new Error("Manual journal creation failed.");
        }
        return {
            result: createdManualJournal,
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
