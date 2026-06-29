import { xeroClient } from "../clients/xero-client.js";
import { formatError } from "../helpers/format-error.js";
import { getClientHeaders } from "../helpers/get-client-headers.js";
async function createItem(itemDetails) {
    await xeroClient.authenticate();
    const item = {
        code: itemDetails.code,
        name: itemDetails.name,
        description: itemDetails.description,
        purchaseDescription: itemDetails.purchaseDescription,
        isPurchased: !!itemDetails.purchaseDetails,
        isSold: !!itemDetails.salesDetails,
        purchaseDetails: itemDetails.purchaseDetails
            ? {
                unitPrice: itemDetails.purchaseDetails.unitPrice,
                taxType: itemDetails.purchaseDetails.taxType,
                accountCode: itemDetails.purchaseDetails.accountCode,
            }
            : undefined,
        salesDetails: itemDetails.salesDetails
            ? {
                unitPrice: itemDetails.salesDetails.unitPrice,
                taxType: itemDetails.salesDetails.taxType,
                accountCode: itemDetails.salesDetails.accountCode,
            }
            : undefined,
        isTrackedAsInventory: itemDetails.isTrackedAsInventory,
        inventoryAssetAccountCode: itemDetails.inventoryAssetAccountCode,
    };
    const items = {
        items: [item],
    };
    const response = await xeroClient.accountingApi.createItems(xeroClient.tenantId, items, // items
    true, // summarizeErrors
    undefined, // unitdp
    undefined, // idempotencyKey
    getClientHeaders());
    return response.body.items?.[0] ?? null;
}
/**
 * Create an item in Xero
 */
export async function createXeroItem(itemDetails) {
    try {
        const item = await createItem(itemDetails);
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
