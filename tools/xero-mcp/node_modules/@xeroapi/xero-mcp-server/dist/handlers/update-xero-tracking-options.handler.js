import { TrackingOption } from "xero-node";
import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
import { getClientHeaders } from "../helpers/get-client-headers.js";
async function getTrackingOptions(trackingCategoryId) {
    await xeroClient.authenticate();
    const response = await xeroClient.accountingApi.getTrackingCategory(xeroClient.tenantId, trackingCategoryId, getClientHeaders());
    return response.body.trackingCategories?.[0].options;
}
async function updateTrackingOption(trackingCategoryId, trackingOptionId, existingTrackingOption, name, status) {
    const trackingOption = {
        trackingOptionID: trackingOptionId,
        name: name ? name : existingTrackingOption.name,
        status: status ? TrackingOption.StatusEnum[status] : existingTrackingOption.status
    };
    await xeroClient.accountingApi.updateTrackingOptions(xeroClient.tenantId, trackingCategoryId, trackingOptionId, trackingOption, undefined, // idempotencyKey
    getClientHeaders());
    return trackingOption;
}
export async function updateXeroTrackingOption(trackingCategoryId, options) {
    try {
        const existingTrackingOptions = await getTrackingOptions(trackingCategoryId);
        if (!existingTrackingOptions) {
            throw new Error("Could not find tracking options.");
        }
        const updatedTrackingOptions = await Promise.all(options?.map(async (option) => {
            const existingTrackingOption = existingTrackingOptions
                .find(existingOption => existingOption.trackingOptionID === option.trackingOptionId);
            return existingTrackingOption
                ? await updateTrackingOption(trackingCategoryId, option.trackingOptionId, existingTrackingOption, option.name, option.status)
                : undefined;
        }));
        if (!updatedTrackingOptions) {
            throw new Error("Failed to update tracking options.");
        }
        return {
            result: updatedTrackingOptions
                .filter(Boolean)
                .map(option => option),
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
