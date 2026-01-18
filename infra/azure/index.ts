/**
 * Azure Infrastructure for Legal-AI OpenAI Batch Processing
 * 
 * This Pulumi program creates:
 * - Resource Group
 * - Azure OpenAI (Cognitive Services) account
 * - GPT-4o model deployment
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
const projectName = "legalai";
const location = config.get("azure-native:location") || "eastus";

// Model deployment configuration
const deployGpt4o = config.getBoolean("deployGpt4o") ?? false;
const deployGpt4oMini = config.getBoolean("deployGpt4oMini") ?? true;
const deployGpt5Mini = config.getBoolean("deployGpt5Mini") ?? true;
const gpt4oCapacity = config.getNumber("gpt4oCapacity") || 20; // TPM in thousands
const gpt4oMiniCapacity = config.getNumber("gpt4oMiniCapacity") || 50; // TPM in thousands
const gpt5MiniCapacity = config.getNumber("gpt5MiniCapacity") || 50; // TPM in thousands

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

// Create Azure OpenAI (Cognitive Services) Account
const openaiAccount = new azure.cognitiveservices.Account(`${projectName}-azure-openai-${environment}`, {
    accountName: `${projectName}-azure-openai-${environment}`,
    resourceGroupName: resourceGroup.name,
    location: location,
    kind: "OpenAI",
    sku: {
        name: "S0", // Standard tier
    },
    properties: {
        customSubDomainName: `${projectName}-azure-openai-${environment}-1`,
        publicNetworkAccess: "Enabled",
    },
    tags: commonTags,
});

// Deploy GPT-4o model (optional)
const gpt4oDeployment = deployGpt4o
    ? new azure.cognitiveservices.Deployment(`${projectName}-gpt4o-deployment`, {
          deploymentName: "gpt-4o",
          accountName: openaiAccount.name,
          resourceGroupName: resourceGroup.name,
          properties: {
              model: {
                  format: "OpenAI",
                  name: "gpt-4o",
                  version: "2024-08-06",
              },
          },
          sku: {
              name: "Standard",
              capacity: gpt4oCapacity,
          },
      })
    : undefined;

// Deploy GPT-4o-mini model (optional)
const gpt4oMiniDeployment = deployGpt4oMini
    ? new azure.cognitiveservices.Deployment(`${projectName}-gpt4omini-deployment`, {
          deploymentName: "gpt-4o-mini",
          accountName: openaiAccount.name,
          resourceGroupName: resourceGroup.name,
          properties: {
              model: {
                  format: "OpenAI",
                  name: "gpt-4o-mini",
                  version: "2024-07-18", // Latest stable version
              },
          },
          sku: {
              name: "Standard",
              capacity: gpt4oMiniCapacity,
          },
      })
    : undefined;

// Deploy GPT-4o-mini GlobalBatch model for batch processing
const gpt4oMiniBatchDeployment = deployGpt4oMini
    ? new azure.cognitiveservices.Deployment(`${projectName}-gpt4omini-batch-deployment`, {
          deploymentName: "gpt-4o-mini-batch",
          accountName: openaiAccount.name,
          resourceGroupName: resourceGroup.name,
          properties: {
              model: {
                  format: "OpenAI",
                  name: "gpt-4o-mini",
                  version: "2024-07-18",
              },
          },
          sku: {
              name: "GlobalBatch",
              capacity: 250, // 250K TPM (tokens per minute) for batch
          },
      })
    : undefined;

// Deploy GPT-5 mini model (default)
const gpt5MiniDeployment = deployGpt5Mini
    ? new azure.cognitiveservices.Deployment(`${projectName}-gpt5mini-deployment`, {
          deploymentName: "gpt-5-mini",
          accountName: openaiAccount.name,
          resourceGroupName: resourceGroup.name,
          properties: {
              model: {
                  format: "OpenAI",
                  name: "gpt-5-mini",
                  version: "2025-08-07", // GPT-5 release version
              },
          },
          sku: {
              name: "Standard",
              capacity: gpt5MiniCapacity,
          },
      })
    : undefined;

// Get OpenAI account keys
const openaiKeys = pulumi
    .all([resourceGroup.name, openaiAccount.name])
    .apply(([rgName, accountName]) =>
        azure.cognitiveservices.listAccountKeys({
            resourceGroupName: rgName,
            accountName: accountName,
        })
    );

// Create Storage Account for batch processing
const storageAccountNameValue = `${projectName}stg${environment}`.substring(0, 24).toLowerCase();
const storageAccount = new azure.storage.StorageAccount(`${projectName}storage${environment}`, {
    accountName: storageAccountNameValue,
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

// Assign "Cognitive Services OpenAI User" role to Service Principal
const openaiRoleAssignment = new azure.authorization.RoleAssignment(`${projectName}-openai-role`, {
    principalId: servicePrincipal.objectId,
    principalType: azure.authorization.PrincipalType.ServicePrincipal,
    roleDefinitionId: pulumi.interpolate`/subscriptions/${clientConfig.then(c => c.subscriptionId)}/providers/Microsoft.Authorization/roleDefinitions/5e0bd9bd-7b93-4f28-af87-19fc36ad61bd`,
    scope: openaiAccount.id,
});

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
const storageConnectionStringValue = pulumi
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

export const storageConnectionString = pulumi.secret(storageConnectionStringValue);
export const storageAccountKey = pulumi.secret(
    storageAccountKeys.apply(keys => keys.keys[0].value)
);

export const servicePrincipalClientId = app.clientId;
export const servicePrincipalTenantId = servicePrincipal.applicationTenantId;
export const servicePrincipalClientSecret = pulumi.secret(spPassword.value);
export const servicePrincipalObjectId = servicePrincipal.objectId;

export const inputContainerUrl = pulumi.interpolate`https://${storageAccount.name}.blob.core.windows.net/${inputContainer.name}`;
export const outputContainerUrl = pulumi.interpolate`https://${storageAccount.name}.blob.core.windows.net/${outputContainer.name}`;

// Azure OpenAI outputs
export const openaiAccountName = openaiAccount.name;
export const openaiAccountId = openaiAccount.id;
export const openaiEndpoint = openaiAccount.properties.endpoint;
export const openaiApiKey = pulumi.secret(
    openaiKeys.apply(keys => keys.key1!)
);
export const gpt4oDeploymentName = gpt4oDeployment?.name || pulumi.output("gpt-4o");
export const gpt4oMiniDeploymentName = gpt4oMiniDeployment?.name || pulumi.output("gpt-4o-mini");
export const gpt4oMiniBatchDeploymentName = gpt4oMiniBatchDeployment?.name || pulumi.output("gpt-4o-mini-batch");
export const gpt5MiniDeploymentName = gpt5MiniDeployment?.name || pulumi.output("gpt-5-mini");
