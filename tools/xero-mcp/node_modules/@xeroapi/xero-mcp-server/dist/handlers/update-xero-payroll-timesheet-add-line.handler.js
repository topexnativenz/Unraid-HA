import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
async function addTimesheetLine(timesheetID, timesheetLine) {
    await xeroClient.authenticate();
    // Call the createTimesheetLine endpoint from the PayrollNZApi
    const createdLine = await xeroClient.payrollNZApi.createTimesheetLine(xeroClient.tenantId, timesheetID, timesheetLine);
    return createdLine.body.timesheetLine ?? null;
}
/**
 * Add a timesheet line to an existing payroll timesheet in Xero
 */
export async function updateXeroPayrollTimesheetAddLine(timesheetID, timesheetLine) {
    try {
        const newLine = await addTimesheetLine(timesheetID, timesheetLine);
        return {
            result: newLine,
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
