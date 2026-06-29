export const formatLineItem = (lineItem) => {
    return [
        `Item ID: ${lineItem.item}`,
        `Item Code: ${lineItem.itemCode}`,
        `Description: ${lineItem.description}`,
        `Quantity: ${lineItem.quantity}`,
        `Unit Amount: ${lineItem.unitAmount}`,
        `Account Code: ${lineItem.accountCode}`,
        `Tax Type: ${lineItem.taxType}`,
        `Tracking: ${lineItem.tracking}`,
        `Line Amount: ${lineItem.lineAmount}`,
    ].join("\n");
};
