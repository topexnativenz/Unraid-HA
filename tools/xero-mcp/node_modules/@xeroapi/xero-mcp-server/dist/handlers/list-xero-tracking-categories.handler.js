import { xeroClient } from "../clients/xero-client.js";
import { getClientHeaders } from "../helpers/get-client-headers.js";
import { formatError } from "../helpers/format-error.js";
async function getTrackingCategories(includeArchived) {
    await xeroClient.authenticate();
    const response = await xeroClient.accountingApi.getTrackingCategories(xeroClient.tenantId, // xeroTenantId
    undefined, // where
    undefined, // order
    includeArchived, // includeArchived
    getClientHeaders());
    return response.body.trackingCategories ?? [];
}
export async function listXeroTrackingCategories(includeArchived) {
    try {
        const trackingCategories = await getTrackingCategories(includeArchived);
        return {
            result: trackingCategories,
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
