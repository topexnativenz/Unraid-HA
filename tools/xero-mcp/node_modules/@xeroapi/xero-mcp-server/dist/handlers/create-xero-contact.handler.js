import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
import { Phone } from "xero-node";
import { getClientHeaders } from "../helpers/get-client-headers.js";
async function createContact(name, email, phone) {
    await xeroClient.authenticate();
    const contact = {
        name,
        emailAddress: email,
        phones: phone
            ? [
                {
                    phoneNumber: phone,
                    phoneType: Phone.PhoneTypeEnum.MOBILE,
                },
            ]
            : undefined,
    };
    const response = await xeroClient.accountingApi.createContacts(xeroClient.tenantId, {
        contacts: [contact],
    }, //contacts
    true, //summarizeErrors
    undefined, //idempotencyKey
    getClientHeaders());
    return response.body.contacts?.[0];
}
/**
 * Create a new invoice in Xero
 */
export async function createXeroContact(name, email, phone) {
    try {
        const createdContact = await createContact(name, email, phone);
        if (!createdContact) {
            throw new Error("Contact creation failed.");
        }
        return {
            result: createdContact,
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
