/**
 * Azure Infrastructure for Legal-AI OpenAI Batch Processing
 * 
 * This Pulumi program creates:
 * - Resource Group
 * - Storage Account with containers for batch input/output
 * - Service Principal with proper RBAC
 * - Role assignments for Azure OpenAI and Storage access
 */

import * as pulumi from "@pulumi/pulumi";
import * as azure from "@pulumi/azure-native";
import * as azuread from "@pulumi/azuread";

// Configuration
const config = new pulumi.Config();
const environment = config.get("environment") || "dev";
const projectName = "legal-ai";
const location = config.get("azure-native:location") || "southeastasia";

// OpenAI resource configuration (assumes it already exists)
const openaiResourceName = config.get("openaiResourceName") || `${projectName}-openai-${environment}`;
const openaiResourceGroup = config.get("openaiResourceGroup");

// Common tags
const commonTags = {
    Project: projectName,
    Environment: environment,
    ManagedBy: "Pulumi",
};

// Get current Azure subscription
const clientConfig = azure.authorization.getClientConfig({});

// Create Resource Group
const resourceGroup = new azure.resources.ResourceGroup(`${projectName}-rg-${environment}`, {
    resourceGroupName: `${projectName}-rg-${environment}`,
    location: location,
    tags: commonTags,
});

// Create Storage Account for batch processing
const storageAccountName = `${projectName}storage${environment}`.substring(0, 24).toLowerCase();
const storageAccount = new azure.storage.StorageAccount(`${projectName}storage${environment}`, {
    accountName: storageAccountName,
    resourceGroupName: resourceGroup.name,
    location: location,
    sku: {
        name: azure.storage.SkuName.Standard_LRS,
    },
    kind: azure.storage.Kind.StorageV2,
    enableHttpsTrafficOnly: true,
    minimumTlsVersion: azure.storage.MinimumTlsVersion.TLS1_2,
    allowBlobPublicAccess: false,
    tags: commonTags,
});

// Create blob container for batch inputs
const inputContainer = new azure.storage.BlobContainer(`${projectName}-batch-input`, {
    containerName: "batch-input",
    accountName: storageAccount.name,
    resourceGroupName: resourceGroup.name,
    publicAccess: azure.storage.PublicAccess.None,
});

// Create blob container for batch outputs
const outputContainer = new azure.storage.BlobContainer(`${projectName}-batch-output`, {
    containerName: "batch-output",
    accountName: storageAccount.name,
    resourceGroupName: resourceGroup.name,
    publicAccess: azure.storage.PublicAccess.None,
});

// Configure lifecycle management to delete old files after 90 days
const lifecyclePolicy = new azure.storage.ManagementPolicy(`${projectName}-lifecycle-policy`, {
    accountName: storageAccount.name,
    resourceGroupName: resourceGroup.name,
    managementPolicyName: "default",
    policy: {
        rules: [{
            enabled: true,
            name: "delete-old-batches",
            type: azure.storage.RuleType.Lifecycle,
            definition: {
                actions: {
                    baseBlob: {
                        delete: {
                            daysAfterModificationGreaterThan: 90,
                        },
                    },
                },
                filters: {
                    blobTypes: ["blockBlob"],
                    prefixMatch: ["batch-input/", "batch-output/"],
                },
            },
        }],
    },
});

// Create Azure AD Application for the service principal
const app = new azuread.Application(`${projectName}-batch-app`, {
    displayName: `${projectName}-batch-app-${environment}`,
});

// Create Service Principal
const servicePrincipal = new azuread.ServicePrincipal(`${projectName}-batch-sp`, {
    clientId: app.clientId,
});

// Create Service Principal Password (Client Secret)
const spPassword = new azuread.ServicePrincipalPassword(`${projectName}-batch-sp-password`, {
    servicePrincipalId: servicePrincipal.id,
    endDateRelative: "8760h", // 1 year
});

// Assign "Storage Blob Data Contributor" role to Service Principal
const storageRoleAssignment = new azure.authorization.RoleAssignment(`${projectName}-storage-role`, {
    principalId: servicePrincipal.objectId,
    principalType: azure.authorization.PrincipalType.ServicePrincipal,
    roleDefinitionId: pulumi.interpolate`/subscriptions/${clientConfig.then(c => c.subscriptionId)}/providers/Microsoft.Authorization/roleDefinitions/ba92f5b4-2d11-453d-a403-e96b0029c9fe`,
    scope: storageAccount.id,
});

// Assign "Cognitive Services OpenAI User" role to Service Principal (if OpenAI resource group is provided)
const openaiRoleAssignment = openaiResourceGroup
    ? new azure.authorization.RoleAssignment(`${projectName}-openai-role`, {
          principalId: servicePrincipal.objectId,
          principalType: azure.authorization.PrincipalType.ServicePrincipal,
          roleDefinitionId: pulumi.interpolate`/subscriptions/${clientConfig.then(c => c.subscriptionId)}/providers/Microsoft.Authorization/roleDefinitions/5e0bd9bd-7b93-4f28-af87-19fc36ad61bd`,
          scope: pulumi.interpolate`/subscriptions/${clientConfig.then(c => c.subscriptionId)}/resourceGroups/${openaiResourceGroup}/providers/Microsoft.CognitiveServices/accounts/${openaiResourceName}`,
      })
    : undefined;

// Get storage account keys
const storageAccountKeys = pulumi
    .all([resourceGroup.name, storageAccount.name])
    .apply(([rgName, saName]) =>
        azure.storage.listStorageAccountKeys({
            resourceGroupName: rgName,
            accountName: saName,
        })
    );

// Construct storage connection string
const storageConnectionString = pulumi
    .all([storageAccount.name, storageAccountKeys])
    .apply(
        ([name, keys]) =>
            `DefaultEndpointsProtocol=https;AccountName=${name};AccountKey=${keys.keys[0].value};EndpointSuffix=core.windows.net`
    );

// Exports
export const resourceGroupName = resourceGroup.name;
export const storageAccountName = storageAccount.name;
export const storageAccountId = storageAccount.id;
export const inputContainerName = inputContainer.name;
export const outputContainerName = outputContainer.name;

export const storageConnectionString = pulumi.secret(storageConnectionString);
export const storageAccountKey = pulumi.secret(
    storageAccountKeys.apply(keys => keys.keys[0].value)
);

export const servicePrincipalClientId = app.clientId;
export const servicePrincipalTenantId = servicePrincipal.applicationTenantId;
export const servicePrincipalClientSecret = pulumi.secret(spPassword.value);
export const servicePrincipalObjectId = servicePrincipal.objectId;

export const inputContainerUrl = pulumi.interpolate`https://${storageAccount.name}.blob.core.windows.net/${inputContainer.name}`;
export const outputContainerUrl = pulumi.interpolate`https://${storageAccount.name}.blob.core.windows.net/${outputContainer.name}`;
