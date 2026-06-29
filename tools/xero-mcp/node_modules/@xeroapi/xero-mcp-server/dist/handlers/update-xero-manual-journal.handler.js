import { xeroClient } from "../clients/xero-client.js";
import { getClientHeaders } from "../helpers/get-client-headers.js";
import { formatError } from "../helpers/format-error.js";
async function updateManualJournal(narration, manualJournalID, manualJournalLines, date, lineAmountTypes, status, url, showOnCashBasisReports) {
    await xeroClient.authenticate();
    const manualJournal = {
        narration,
        journalLines: manualJournalLines.map((journalLine) => ({
            lineAmount: journalLine.lineAmount,
            accountCode: journalLine.accountCode,
            description: journalLine.description, // Optional: description for the manual journal line
            taxType: journalLine.taxType, // Optional: tax type for the manual journal line
            // TODO: tracking can be added here
        })),
        date: date, // Optional: YYYY-MM-DD format
        lineAmountTypes: lineAmountTypes, // Optional: ManualJournal.LineAmountTypesEnum.EXCLUSIVE
        status: status, // Optional: ManualJournal.StatusEnum.DRAFT
        url: url, // Optional: URL link to a source document
        showOnCashBasisReports: showOnCashBasisReports, // Optional: default is true if not specified
    };
    const manualJournals = {
        manualJournals: [manualJournal],
    };
    const response = await xeroClient.accountingApi.updateManualJournal(xeroClient.tenantId, manualJournalID, manualJournals, undefined, getClientHeaders());
    return response.body.manualJournals?.[0];
}
export async function updateXeroManualJournal(narration, manualJournalID, manualJournalLines, date, lineAmountTypes, status, url, showOnCashBasisReports) {
    try {
        const updatedManualJournal = await updateManualJournal(narration, manualJournalID, manualJournalLines, date, lineAmountTypes, status, url, showOnCashBasisReports);
        if (!updatedManualJournal) {
            throw new Error("Manual journal update failed.");
        }
        return {
            result: updatedManualJournal,
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
