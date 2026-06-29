import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
async function getTimesheet(timesheetID) {
    await xeroClient.authenticate();
    // Call the Timesheet endpoint from the PayrollNZApi
    const timesheet = await xeroClient.payrollNZApi.getTimesheet(xeroClient.tenantId, timesheetID);
    return timesheet.body.timesheet ?? null;
}
/**
 * Get a single payroll timesheet from Xero
 */
export async function getXeroPayrollTimesheet(timesheetID) {
    try {
        const timesheet = await getTimesheet(timesheetID);
        return {
            result: timesheet,
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
