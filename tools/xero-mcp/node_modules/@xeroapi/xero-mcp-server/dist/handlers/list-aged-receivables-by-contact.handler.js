import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
import { getClientHeaders } from "../helpers/get-client-headers.js";
async function listAgedReceivablesByContact(contactId, reportDate, invoicesFromDate, invoicesToDate) {
    await xeroClient.authenticate();
    const response = await xeroClient.accountingApi.getReportAgedReceivablesByContact(xeroClient.tenantId, // xeroTenantId
    contactId, // contactId
    reportDate, // date
    invoicesFromDate, // fromDate
    invoicesToDate, // toDate
    getClientHeaders());
    return response.body.reports?.[0];
}
export async function listXeroAgedReceivablesByContact(contactId, reportDate, invoicesFromDate, invoicesToDate) {
    try {
        const agedReceivables = await listAgedReceivablesByContact(contactId, reportDate, invoicesFromDate, invoicesToDate);
        if (!agedReceivables) {
            return {
                result: null,
                isError: true,
                error: "Failed to get aged receivables by contact from Xero."
            };
        }
        return {
            result: agedReceivables,
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
