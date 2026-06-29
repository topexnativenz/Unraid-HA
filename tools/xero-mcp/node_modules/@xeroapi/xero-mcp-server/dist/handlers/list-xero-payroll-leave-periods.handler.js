import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
/**
 * Internal function to fetch employee leave periods from Xero
 */
async function fetchLeavePeriods({ employeeId, startDate, endDate, }) {
    await xeroClient.authenticate();
    if (!employeeId) {
        throw new Error("Employee ID is required to fetch leave periods");
    } // After reviewing the SDK documentation, it appears this API call requires different parameters
    // Use parameters that match the SDK's expectations
    const response = await xeroClient.payrollNZApi.getEmployeeLeavePeriods(xeroClient.tenantId, employeeId, startDate, endDate);
    return response.body.periods ?? null;
}
/**
 * List employee leave periods from Xero Payroll
 * @param employeeId The ID of the employee to retrieve leave periods for
 * @param startDate Optional start date in YYYY-MM-DD format
 * @param endDate Optional end date in YYYY-MM-DD format
 */
export async function listXeroPayrollLeavePeriods(employeeId, startDate, endDate) {
    try {
        const periods = await fetchLeavePeriods({ employeeId, startDate, endDate });
        if (!periods) {
            return {
                result: [],
                isError: false,
                error: null,
            };
        }
        return {
            result: periods,
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
