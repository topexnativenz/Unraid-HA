import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
import { Phone, Address } from "xero-node";
import { getClientHeaders } from "../helpers/get-client-headers.js";
async function updateContact(name, firstName, lastName, email, phone, address, contactId) {
    await xeroClient.authenticate();
    const contact = {
        name,
        firstName,
        lastName,
        emailAddress: email,
        phones: phone
            ? [
                {
                    phoneNumber: phone,
                    phoneType: Phone.PhoneTypeEnum.MOBILE,
                },
            ]
            : undefined,
        addresses: address
            ? [
                {
                    addressType: Address.AddressTypeEnum.STREET,
                    addressLine1: address.addressLine1,
                    addressLine2: address.addressLine2,
                    city: address.city,
                    country: address.country,
                    postalCode: address.postalCode,
                    region: address.region,
                },
            ]
            : undefined,
    };
    const contacts = {
        contacts: [contact],
    };
    const response = await xeroClient.accountingApi.updateContact(xeroClient.tenantId, contactId, // contactId
    contacts, // contacts
    undefined, // idempotencyKey
    getClientHeaders());
    const updatedContact = response.body.contacts?.[0];
    return updatedContact;
}
/**
 * Create a new invoice in Xero
 */
export async function updateXeroContact(contactId, name, firstName, lastName, email, phone, address) {
    try {
        const updatedContact = await updateContact(name, firstName, lastName, email, phone, address, contactId);
        if (!updatedContact) {
            throw new Error("Contact update failed.");
        }
        return {
            result: updatedContact,
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
