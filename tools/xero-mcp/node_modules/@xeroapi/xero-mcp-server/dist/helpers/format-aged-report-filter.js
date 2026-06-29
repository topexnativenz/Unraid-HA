export const formatAgedReportFilter = (fromDate, toDate) => {
    if (!fromDate && !toDate) {
        return undefined;
    }
    const formattedFromDate = fromDate ? `from ${fromDate}` : "";
    const formattedToDate = toDate ? `to ${toDate}` : "";
    return `Showing invoices ${formattedFromDate} ${formattedToDate}`;
};
