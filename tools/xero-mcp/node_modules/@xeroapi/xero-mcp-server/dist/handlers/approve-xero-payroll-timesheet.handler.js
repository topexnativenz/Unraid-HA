import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
async function approveTimesheet(timesheetID) {
    await xeroClient.authenticate();
    // Call the approveTimesheet endpoint from the PayrollNZApi
    const approvedTimesheet = await xeroClient.payrollNZApi.approveTimesheet(xeroClient.tenantId, timesheetID);
    return approvedTimesheet.body.timesheet ?? null;
}
/**
 * Approve a payroll timesheet in Xero
 */
export async function approveXeroPayrollTimesheet(timesheetID) {
    try {
        const approvedTimesheet = await approveTimesheet(timesheetID);
        return {
            result: approvedTimesheet,
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
