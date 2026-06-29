import { xeroClient } from "../clients/xero-client.js";
import { contactDeepLink, creditNoteDeepLink, invoiceDeepLink, paymentDeepLink, manualJournalDeepLink, quoteDeepLink, billDeepLink, } from "../consts/deeplinks.js";
export var DeepLinkType;
(function (DeepLinkType) {
    DeepLinkType[DeepLinkType["CONTACT"] = 0] = "CONTACT";
    DeepLinkType[DeepLinkType["CREDIT_NOTE"] = 1] = "CREDIT_NOTE";
    DeepLinkType[DeepLinkType["INVOICE"] = 2] = "INVOICE";
    DeepLinkType[DeepLinkType["MANUAL_JOURNAL"] = 3] = "MANUAL_JOURNAL";
    DeepLinkType[DeepLinkType["QUOTE"] = 4] = "QUOTE";
    DeepLinkType[DeepLinkType["PAYMENT"] = 5] = "PAYMENT";
    DeepLinkType[DeepLinkType["BILL"] = 6] = "BILL";
})(DeepLinkType || (DeepLinkType = {}));
/**
 * Gets a deep link for a specific type and item ID.
 * This will also fetch the org short code from the Xero client.
 * @param type
 * @param itemId
 * @returns
 */
export const getDeepLink = async (type, itemId) => {
    const orgShortCode = await xeroClient.getShortCode();
    if (!orgShortCode) {
        throw new Error("Failed to retrieve organisation short code");
    }
    switch (type) {
        case DeepLinkType.CONTACT:
            return contactDeepLink(orgShortCode, itemId);
        case DeepLinkType.CREDIT_NOTE:
            return creditNoteDeepLink(orgShortCode, itemId);
        case DeepLinkType.MANUAL_JOURNAL:
            return manualJournalDeepLink(itemId);
        case DeepLinkType.INVOICE:
            return invoiceDeepLink(orgShortCode, itemId);
        case DeepLinkType.QUOTE:
            return quoteDeepLink(orgShortCode, itemId);
        case DeepLinkType.PAYMENT:
            return paymentDeepLink(orgShortCode, itemId);
        case DeepLinkType.BILL:
            return billDeepLink(orgShortCode, itemId);
    }
};
