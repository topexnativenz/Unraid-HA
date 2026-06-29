import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
import { getClientHeaders } from "../helpers/get-client-headers.js";
async function createTrackingCategory(name) {
    xeroClient.authenticate();
    const trackingCategory = {
        name: name
    };
    const response = await xeroClient.accountingApi.createTrackingCategory(xeroClient.tenantId, // xeroTenantId
    trackingCategory, undefined, // idempotencyKey
    getClientHeaders() // options
    );
    const createdTrackingCategory = response.body.trackingCategories?.[0];
    return createdTrackingCategory;
}
export async function createXeroTrackingCategory(name) {
    try {
        const createdTrackingCategory = await createTrackingCategory(name);
        if (!createdTrackingCategory) {
            throw new Error("Tracking Category creation failed.");
        }
        return {
            result: createdTrackingCategory,
            isError: false,
            error: null
        };
    }
    catch (error) {
        return {
            result: null,
            isError: true,
            error: formatError(error)
        };
    }
}
