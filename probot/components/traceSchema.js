export const traceSchema = {
    "type": "object",
    "properties": {
        "date": { "type": "string" },
        "deviceDimensions": { "type": "string" },
        "executionType": { "type": "string" },
        "executionNum": { "type": "integer" },
        "crash": { "type": "boolean" },
        "deviceName": { "type": "string" },
        "elapsedTime": { "type": "integer" },
        "orientation": { "type": "integer" },
        "mainActivity": { "type": "string" },
        "androidVersion": { "type": "string" },
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": { "type": "integer" },
                    "sequenceStep": { "type": "integer" },
                    "screenshot": { "type": "string" },
                    "textEntry": { "type": "string" },
                    "areaEdit": { "type": "integer" },
                    "hashStep": { "type": "string" },
                    "areaView": { "type": "integer" },
                    "areaList": { "type": "integer" },
                    "areaSelect": { "type": "integer" },
                    "initialX": { "type": "integer" },
                    "initialY": { "type": "integer" },
                    "finalX": { "type": "integer" },
                    "finalY": { "type": "integer" },
                    "useCaseTranType": { "type": "integer" },
                    "network": { "type": "boolean" },
                    "acellerometer": { "type": "boolean" },
                    "magentometer": { "type": "boolean" },
                    "temperature": { "type": "boolean" },
                    "gps": { "type": "boolean" }
                },
                "required": ["action", "sequenceStep", "screenshot"]
            }
        },
        "app": {
            "type": "object",
            "properties": {
                "name": { "type": "string" },
                "packageName": { "type": "string" },
                "mainActivity": { "type": "string" },
                "version": { "type": "string" },
                "apkPath": { "type": "string" }
            },
            "required": ["name", "packageName", "mainActivity", "version", "apkPath"]
        }
    },
    "required": ["date", "deviceDimensions", "executionType", "executionNum", "crash", "deviceName", "elapsedTime", "orientation", "mainActivity", "androidVersion", "steps", "app"]
};