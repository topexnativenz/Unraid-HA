import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
export class XeroMcpServer {
    static instance = null;
    constructor() { }
    static GetServer() {
        if (XeroMcpServer.instance === null) {
            XeroMcpServer.instance = new McpServer({
                name: "Xero MCP Server",
                version: "1.0.0",
            });
        }
        return XeroMcpServer.instance;
    }
}
