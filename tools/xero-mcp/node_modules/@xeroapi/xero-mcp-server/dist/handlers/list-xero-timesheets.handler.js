import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
async function getTimesheets() {
    await xeroClient.authenticate();
    // Call the Timesheets endpoint from the PayrollNZApi
    const timesheets = await xeroClient.payrollNZApi.getTimesheets(xeroClient.tenantId, undefined, // page
    undefined);
    return timesheets.body.timesheets ?? [];
}
/**
 * List all payroll timesheets from Xero
 */
export async function listXeroPayrollTimesheets() {
    try {
        const timesheets = await getTimesheets();
        return {
            result: timesheets,
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
