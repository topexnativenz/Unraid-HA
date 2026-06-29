export const invoiceDeepLink = (orgShortCode, invoiceId) => {
    return ` https://go.xero.com/app/${orgShortCode}/invoicing/view/${invoiceId}`;
};
export const contactDeepLink = (orgShortCode, contactId) => {
    return ` https://go.xero.com/app/${orgShortCode}/contacts/contact/${contactId}`;
};
export const creditNoteDeepLink = (orgShortCode, creditNoteId) => {
    return `https://go.xero.com/organisationlogin/default.aspx?shortcode=${orgShortCode}&redirecturl=/AccountsPayable/ViewCreditNote.aspx?creditNoteID=${creditNoteId}`;
};
export const quoteDeepLink = (orgShortCode, quoteId) => {
    return `https://go.xero.com/app/${orgShortCode}/quotes/view/${quoteId}`;
};
export const paymentDeepLink = (orgShortCode, paymentId) => {
    return `https://go.xero.com/organisationlogin/default.aspx?shortcode=${orgShortCode}&redirecturl=/Bank/ViewTransaction.aspx?bankTransactionID=${paymentId}`;
};
export const bankTransactionDeepLink = (accountId, bankTransactionId) => {
    return `https://go.xero.com/Bank/ViewTransaction.aspx?bankTransactionID=${bankTransactionId}&accountID=${accountId}`;
};
export const manualJournalDeepLink = (journalId) => {
    return `https://go.xero.com/Journal/View.aspx?invoiceID=${journalId}`;
};
export const billDeepLink = (orgShortCode, billId) => {
    return `https://go.xero.com/organisationlogin/default.aspx?shortcode=${orgShortCode}&redirecturl=/AccountsPayable/Edit.aspx?InvoiceID=${billId}`;
};
