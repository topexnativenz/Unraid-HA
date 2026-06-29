import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
async function revertTimesheet(timesheetID) {
    await xeroClient.authenticate();
    // Call the revertTimesheet endpoint from the PayrollNZApi
    const revertedTimesheet = await xeroClient.payrollNZApi.revertTimesheet(xeroClient.tenantId, timesheetID);
    return revertedTimesheet.body.timesheet ?? null;
}
/**
 * Revert a payroll timesheet to draft in Xero
 */
export async function revertXeroPayrollTimesheet(timesheetID) {
    try {
        const revertedTimesheet = await revertTimesheet(timesheetID);
        return {
            result: revertedTimesheet,
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
