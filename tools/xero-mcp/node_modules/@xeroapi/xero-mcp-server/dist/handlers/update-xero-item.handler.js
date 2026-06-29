import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
import { getClientHeaders } from "../helpers/get-client-headers.js";
async function updateItem(itemId, itemDetails) {
    await xeroClient.authenticate();
    const item = {
        code: itemDetails.code,
        name: itemDetails.name,
        description: itemDetails.description,
        purchaseDescription: itemDetails.purchaseDescription,
        purchaseDetails: itemDetails.purchaseDetails,
        salesDetails: itemDetails.salesDetails,
        isTrackedAsInventory: itemDetails.isTrackedAsInventory,
        inventoryAssetAccountCode: itemDetails.inventoryAssetAccountCode,
    };
    const items = {
        items: [item],
    };
    const response = await xeroClient.accountingApi.updateItem(xeroClient.tenantId, itemId, items, undefined, // unitdp
    undefined, // idempotencyKey
    getClientHeaders());
    return response.body.items?.[0] ?? null;
}
/**
 * Update an item in Xero
 * @param itemId - The ID of the item to update
 * @param itemDetails - The details to update on the item
 * @returns A response containing the updated item or error details
 */
export async function updateXeroItem(itemId, itemDetails) {
    try {
        const item = await updateItem(itemId, itemDetails);
        return {
            result: item,
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
