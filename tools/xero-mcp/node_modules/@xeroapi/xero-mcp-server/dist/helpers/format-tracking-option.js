export const formatTrackingOption = (option) => {
    return [
        `Option ID: ${option.trackingOptionID}`,
        `Name: ${option.name}`,
        `Status: ${option.status}`
    ].join("\n");
};
