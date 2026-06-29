import { TrackingCategory } from "xero-node";
import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
import { getClientHeaders } from "../helpers/get-client-headers.js";
async function getTrackingCategory(trackingCategoryId) {
    await xeroClient.authenticate();
    const response = await xeroClient.accountingApi.getTrackingCategory(xeroClient.tenantId, trackingCategoryId, getClientHeaders());
    return response.body.trackingCategories?.[0];
}
async function updateTrackingCategory(trackingCategoryId, existingTrackingCategory, name, status) {
    const trackingCategory = {
        trackingCategoryID: trackingCategoryId,
        name: name ? name : existingTrackingCategory.name,
        status: status ? TrackingCategory.StatusEnum[status] : existingTrackingCategory.status
    };
    await xeroClient.accountingApi.updateTrackingCategory(xeroClient.tenantId, trackingCategoryId, trackingCategory, undefined, // idempotencyKey
    getClientHeaders());
    return trackingCategory;
}
export async function updateXeroTrackingCategory(trackingCategoryId, name, status) {
    try {
        const existingTrackingCategory = await getTrackingCategory(trackingCategoryId);
        if (!existingTrackingCategory) {
            throw new Error("Could not find tracking category.");
        }
        const updatedTrackingCategory = await updateTrackingCategory(trackingCategoryId, existingTrackingCategory, name, status);
        if (!updatedTrackingCategory) {
            throw new Error("Failed to update tracking category.");
        }
        return {
            result: existingTrackingCategory,
            isError: false,
            error: null
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
