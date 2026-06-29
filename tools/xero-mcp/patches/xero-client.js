import fs from "fs";
import os from "os";
import path from "path";
import axios from "axios";
import dotenv from "dotenv";
import { XeroClient, } from "xero-node";
import { ensureError } from "../helpers/ensure-error.js";
dotenv.config();
const client_id = process.env.XERO_CLIENT_ID;
const client_secret = process.env.XERO_CLIENT_SECRET;
const bearer_token = process.env.XERO_CLIENT_BEARER_TOKEN;
const grant_type = "client_credentials";
if (!bearer_token && (!client_id || !client_secret)) {
    throw Error("Environment Variables not set - please check your .env file");
}
function resolveActiveTenantId() {
    if (process.env.XERO_TENANT_ID) {
        return process.env.XERO_TENANT_ID;
    }
    try {
        const activeFile = path.join(os.homedir(), ".config", "xero-mcp", "active-org.json");
        const active = JSON.parse(fs.readFileSync(activeFile, "utf8"));
        return active.tenant_id || null;
    }
    catch {
        return null;
    }
}
class MCPXeroClient extends XeroClient {
    tenantId;
    shortCode;
    constructor(config) {
        super(config);
        this.tenantId = "";
        this.shortCode = "";
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    async updateTenants(fullOrgDetails) {
        await super.updateTenants(fullOrgDetails);
        const forced = resolveActiveTenantId();
        const previous = this.tenantId;
        if (forced) {
            const known = this.tenants?.some((tenant) => tenant.tenantId === forced);
            if (!known) {
                throw new Error(`Active tenant ${forced} is not in connected organisations`);
            }
            this.tenantId = forced;
        }
        else if (this.tenants && this.tenants.length > 0) {
            this.tenantId = this.tenants[0].tenantId;
        }
        if (this.tenantId !== previous) {
            this.shortCode = "";
        }
        return this.tenants;
    }
    async getOrganisation() {
        await this.authenticate();
        const organisationResponse = await this.accountingApi.getOrganisations(this.tenantId || "");
        const organisation = organisationResponse.body.organisations?.[0];
        if (!organisation) {
            throw new Error("Failed to retrieve organisation");
        }
        return organisation;
    }
    async getShortCode() {
        if (!this.shortCode) {
            try {
                const organisation = await this.getOrganisation();
                this.shortCode = organisation.shortCode ?? "";
            }
            catch (error) {
                const err = ensureError(error);
                throw new Error(`Failed to get Organisation short code: ${err.message}`);
            }
        }
        return this.shortCode;
    }
}
class CustomConnectionsXeroClient extends MCPXeroClient {
    clientId;
    clientSecret;
    XERO_DEFAULT_AUTH_SCOPES_V1 = [
        "accounting.transactions",
        "accounting.contacts",
        "accounting.settings",
        "accounting.reports.read",
        "payroll.settings",
        "payroll.employees",
        "payroll.timesheets",
    ].join(" ");
    XERO_DEFAULT_AUTH_SCOPES_V2 = [
        "accounting.invoices",
        "accounting.payments",
        "accounting.banktransactions",
        "accounting.manualjournals",
        "accounting.reports.aged.read",
        "accounting.reports.balancesheet.read",
        "accounting.reports.profitandloss.read",
        "accounting.reports.trialbalance.read",
        "accounting.contacts",
        "accounting.settings",
        "payroll.settings",
        "payroll.employees",
        "payroll.timesheets",
    ].join(" ");
    constructor(config) {
        super(config);
        this.clientId = config.clientId;
        this.clientSecret = config.clientSecret;
    }
    formatTokenError(error, context) {
        const axiosError = error;
        const data = axiosError.response?.data;
        const message = typeof data === "object" ? JSON.stringify(data) : data || axiosError.message;
        return new Error(`Failed to get Xero token${context}: ${message}`);
    }
    async getClientCredentialsToken() {
        if (process.env.XERO_SCOPES) {
            try {
                return await this.requestToken(process.env.XERO_SCOPES);
            }
            catch (envError) {
                throw this.formatTokenError(envError, " with XERO_SCOPES");
            }
        }
        try {
            return await this.requestToken(this.XERO_DEFAULT_AUTH_SCOPES_V1);
        }
        catch (error) {
            const axiosError = error;
            const isInvalidScope = axiosError.response?.status === 400 &&
                axiosError.response?.data?.error === "invalid_scope";
            if (!isInvalidScope) {
                throw this.formatTokenError(error, " with V1 scopes");
            }
            try {
                return await this.requestToken(this.XERO_DEFAULT_AUTH_SCOPES_V2);
            }
            catch (v2Error) {
                throw this.formatTokenError(v2Error, " with V2 scopes");
            }
        }
    }
    async requestToken(scope) {
        const credentials = Buffer.from(`${this.clientId}:${this.clientSecret}`).toString("base64");
        const response = await axios.post("https://identity.xero.com/connect/token", `grant_type=client_credentials&scope=${encodeURIComponent(scope)}`, {
            headers: {
                Authorization: `Basic ${credentials}`,
                "Content-Type": "application/x-www-form-urlencoded",
                Accept: "application/json",
            },
        });
        const token = response.data.access_token;
        const connectionsResponse = await axios.get("https://api.xero.com/connections", {
            headers: {
                Authorization: `Bearer ${token}`,
                Accept: "application/json",
            },
        });
        if (connectionsResponse.data && connectionsResponse.data.length > 0) {
            this.tenantId = connectionsResponse.data[0].tenantId;
        }
        return response.data;
    }
    async authenticate() {
        const tokenResponse = await this.getClientCredentialsToken();
        this.setTokenSet({
            access_token: tokenResponse.access_token,
            expires_in: tokenResponse.expires_in,
            token_type: tokenResponse.token_type,
        });
    }
}
class BearerTokenXeroClient extends MCPXeroClient {
    bearerToken;
    constructor(config) {
        super();
        this.bearerToken = config.bearerToken;
    }
    async authenticate() {
        this.setTokenSet({
            access_token: this.bearerToken,
        });
        await this.updateTenants();
    }
}
export const xeroClient = bearer_token
    ? new BearerTokenXeroClient({
        bearerToken: bearer_token,
    })
    : new CustomConnectionsXeroClient({
        clientId: client_id,
        clientSecret: client_secret,
        grantType: grant_type,
    });
