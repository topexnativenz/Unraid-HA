import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
async function createTimesheet(timesheet) {
    await xeroClient.authenticate();
    // Call the createTimesheet endpoint from the PayrollNZApi
    const createdTimesheet = await xeroClient.payrollNZApi.createTimesheet(xeroClient.tenantId, timesheet);
    return createdTimesheet.body.timesheet ?? null;
}
/**
 * Create a payroll timesheet in Xero
 */
export async function createXeroPayrollTimesheet(timesheet) {
    try {
        const newTimesheet = await createTimesheet(timesheet);
        return {
            result: newTimesheet,
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
