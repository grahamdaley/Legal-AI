/**
 * Unit tests for Azure Pulumi infrastructure
 * Tests that resource names and IDs are exported correctly
 */

import * as pulumi from "@pulumi/pulumi";
import { describe, it, before } from "mocha";
import { expect } from "chai";

// Mock Pulumi runtime for testing
pulumi.runtime.setMocks({
    newResource: function(args: pulumi.runtime.MockResourceArgs): {id: string, state: any} {
        const resourceType = args.type;
        const resourceName = args.name;
        
        // Mock Resource Group
        if (resourceType === "azure-native:resources:ResourceGroup") {
            const rgName = args.inputs.resourceGroupName || resourceName;
            return {
                id: `/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/${rgName}`,
                state: {
                    ...args.inputs,
                    name: rgName,
                    location: args.inputs.location || "southeastasia",
                },
            };
        }
        
        // Mock Storage Account
        if (resourceType === "azure-native:storage:StorageAccount") {
            const accountName = args.inputs.accountName || resourceName.replace(/-/g, "").toLowerCase();
            return {
                id: `/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/legal-ai-rg-dev/providers/Microsoft.Storage/storageAccounts/${accountName}`,
                state: {
                    ...args.inputs,
                    name: accountName,
                },
            };
        }
        
        // Mock Blob Container
        if (resourceType === "azure-native:storage:BlobContainer") {
            const containerName = args.inputs.containerName || resourceName;
            return {
                id: `/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/legal-ai-rg-dev/providers/Microsoft.Storage/storageAccounts/legalaidev/blobServices/default/containers/${containerName}`,
                state: {
                    ...args.inputs,
                    name: containerName,
                },
            };
        }
        
        // Mock Azure AD Application
        if (resourceType === "azuread:index/application:Application") {
            const appId = "00000000-0000-0000-0000-000000000001";
            return {
                id: appId,
                state: {
                    ...args.inputs,
                    clientId: appId,
                    displayName: args.inputs.displayName || resourceName,
                },
            };
        }
        
        // Mock Service Principal
        if (resourceType === "azuread:index/servicePrincipal:ServicePrincipal") {
            const objectId = "11111111-1111-1111-1111-111111111111";
            return {
                id: objectId,
                state: {
                    ...args.inputs,
                    objectId: objectId,
                    applicationTenantId: "22222222-2222-2222-2222-222222222222",
                },
            };
        }
        
        // Mock Service Principal Password
        if (resourceType === "azuread:index/servicePrincipalPassword:ServicePrincipalPassword") {
            return {
                id: "password-id",
                state: {
                    ...args.inputs,
                    value: "mock-client-secret-value",
                },
            };
        }
        
        // Mock other resources
        return {
            id: args.inputs.name || resourceName,
            state: args.inputs,
        };
    },
    call: function(args: pulumi.runtime.MockCallArgs): {outputs: any} {
        // Mock Azure client config
        if (args.token === "azure-native:authorization:getClientConfig") {
            return {
                outputs: {
                    subscriptionId: "12345678-1234-1234-1234-123456789012",
                    tenantId: "22222222-2222-2222-2222-222222222222",
                    clientId: "33333333-3333-3333-3333-333333333333",
                },
            };
        }
        
        // Mock storage account keys
        if (args.token === "azure-native:storage:listStorageAccountKeys") {
            return {
                outputs: {
                    keys: [
                        {
                            keyName: "key1",
                            value: "mockStorageKey123456789==",
                            permissions: "Full",
                        },
                        {
                            keyName: "key2",
                            value: "mockStorageKey987654321==",
                            permissions: "Full",
                        },
                    ],
                },
            };
        }
        
        return {outputs: {}};
    },
});

// Import the infrastructure code after setting up mocks
import * as infra from "./index";

describe("Azure Infrastructure Exports", () => {

    describe("Resource Group", () => {
        it("should export resource group name", async () => {
            const rgName = await new Promise<string>((resolve) => {
                infra.resourceGroupName.apply(v => { resolve(v); return v; });
            });
            expect(rgName).to.be.a("string");
            expect(rgName).to.match(/^legal-ai-rg-/);
        });
    });

    describe("Storage Account", () => {
        it("should export storage account name", async () => {
            const accountName = await new Promise<string>((resolve) => {
                infra.storageAccountName.apply(v => { resolve(v); return v; });
            });
            expect(accountName).to.be.a("string");
            expect(accountName).to.match(/^legal.*storage/);
            expect(accountName.length).to.be.at.most(24);
        });

        it("should export storage account ID", async () => {
            const accountId = await new Promise<string>((resolve) => {
                infra.storageAccountId.apply(v => { resolve(v); return v; });
            });
            expect(accountId).to.be.a("string");
            expect(accountId).to.match(/^\/subscriptions\/[a-f0-9-]+\/resourceGroups\//);
            expect(accountId).to.include("Microsoft.Storage/storageAccounts");
        });

        it("should export storage account key", async () => {
            // Storage account key is a secret Output
            expect(infra.storageAccountKey).to.not.be.undefined;
            expect(pulumi.Output.isInstance(infra.storageAccountKey)).to.be.true;
        });

        it("should export storage connection string", async () => {
            // Storage connection string is a secret Output
            expect(infra.storageConnectionString).to.not.be.undefined;
            expect(pulumi.Output.isInstance(infra.storageConnectionString)).to.be.true;
        });
    });

    describe("Blob Containers", () => {
        it("should export input container name", async () => {
            const containerName = await new Promise<string>((resolve) => {
                infra.inputContainerName.apply(v => { resolve(v); return v; });
            });
            expect(containerName).to.be.a("string");
            expect(containerName).to.equal("batch-input");
        });

        it("should export output container name", async () => {
            const containerName = await new Promise<string>((resolve) => {
                infra.outputContainerName.apply(v => { resolve(v); return v; });
            });
            expect(containerName).to.be.a("string");
            expect(containerName).to.equal("batch-output");
        });

        it("should export input container URL", async () => {
            const containerUrl = await new Promise<string>((resolve) => {
                infra.inputContainerUrl.apply(v => { resolve(v); return v; });
            });
            const accountName = await new Promise<string>((resolve) => {
                infra.storageAccountName.apply(v => { resolve(v); return v; });
            });
            expect(containerUrl).to.be.a("string");
            expect(containerUrl).to.match(/^https:\/\/.*\.blob\.core\.windows\.net\/batch-input$/);
            expect(containerUrl).to.include(accountName);
        });

        it("should export output container URL", async () => {
            const containerUrl = await new Promise<string>((resolve) => {
                infra.outputContainerUrl.apply(v => { resolve(v); return v; });
            });
            const accountName = await new Promise<string>((resolve) => {
                infra.storageAccountName.apply(v => { resolve(v); return v; });
            });
            expect(containerUrl).to.be.a("string");
            expect(containerUrl).to.match(/^https:\/\/.*\.blob\.core\.windows\.net\/batch-output$/);
            expect(containerUrl).to.include(accountName);
        });
    });

    describe("Service Principal", () => {
        it("should export service principal client ID", async () => {
            const clientId = await new Promise<string>((resolve) => {
                infra.servicePrincipalClientId.apply(v => { resolve(v); return v; });
            });
            expect(clientId).to.be.a("string");
            expect(clientId).to.match(/^[a-f0-9-]{36}$/);
        });

        it("should export service principal tenant ID", async () => {
            const tenantId = await new Promise<string>((resolve) => {
                infra.servicePrincipalTenantId.apply(v => { resolve(v); return v; });
            });
            expect(tenantId).to.be.a("string");
            expect(tenantId).to.match(/^[a-f0-9-]{36}$/);
        });

        it("should export service principal client secret", async () => {
            const clientSecret = await new Promise<string>((resolve) => {
                infra.servicePrincipalClientSecret.apply(v => {
                    if (pulumi.Output.isInstance(v)) {
                        v.apply(secret => { resolve(secret as string); return secret; });
                    } else {
                        resolve(v as string);
                    }
                    return v;
                });
            });
            expect(clientSecret).to.be.a("string");
            expect(clientSecret.length).to.be.at.least(10);
        });

        it("should export service principal object ID", async () => {
            const objectId = await new Promise<string>((resolve) => {
                infra.servicePrincipalObjectId.apply(v => { resolve(v); return v; });
            });
            expect(objectId).to.be.a("string");
            expect(objectId).to.match(/^[a-f0-9-]{36}$/);
        });
    });

    describe("Resource Naming Consistency", () => {
        it("should use consistent environment naming across resources", async () => {
            const rgName = await new Promise<string>((resolve) => {
                infra.resourceGroupName.apply(v => { resolve(v); return v; });
            });
            const accountName = await new Promise<string>((resolve) => {
                infra.storageAccountName.apply(v => { resolve(v); return v; });
            });
            const environment = rgName.split("-").pop();
            expect(accountName).to.include(environment!);
        });
    });
});
