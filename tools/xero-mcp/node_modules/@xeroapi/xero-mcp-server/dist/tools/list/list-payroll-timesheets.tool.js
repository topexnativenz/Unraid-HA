import { listXeroPayrollTimesheets, } from "../../handlers/list-xero-timesheets.handler.js";
import { CreateXeroTool } from "../../helpers/create-xero-tool.js";
const ListPayrollTimesheetsTool = CreateXeroTool("list-timesheets", `List all payroll timesheets in Xero.
This retrieves comprehensive timesheet details including timesheet IDs, employee IDs, start and end dates, total hours, and the last updated date.`, {}, async () => {
    const response = await listXeroPayrollTimesheets();
    if (response.isError) {
        return {
            content: [
                {
                    type: "text",
                    text: `Error listing timesheets: ${response.error}`,
                },
            ],
        };
    }
    const timesheets = response.result;
    return {
        content: [
            {
                type: "text",
                text: `Found ${timesheets?.length || 0} timesheets:`,
            },
            ...(timesheets?.map((timesheet) => ({
                type: "text",
                text: [
                    `Timesheet ID: ${timesheet.timesheetID}`,
                    `Employee ID: ${timesheet.employeeID}`,
                    `Start Date: ${timesheet.startDate}`,
                    `End Date: ${timesheet.endDate}`,
                    `Total Hours: ${timesheet.totalHours}`,
                    `Last Updated: ${timesheet.updatedDateUTC}`,
                ]
                    .filter(Boolean)
                    .join("\n"),
            })) || []),
        ],
    };
});
export default ListPayrollTimesheetsTool;
