# Azure Infrastructure for Legal-AI

This directory contains Pulumi Infrastructure as Code (IaC) for provisioning Azure resources needed for Azure OpenAI batch processing.

## What Gets Created

The Pulumi script provisions:

1. **Resource Group**:
   - `legalai-rg-{environment}`: Container for all Azure resources

2. **Azure OpenAI (Cognitive Services)**:
   - Azure OpenAI account (S0 tier)
   - GPT-4o-mini model deployment (default, cost-effective)
   - GPT-4o model deployment (optional, higher quality)
   - Custom subdomain for API endpoint

3. **Storage Account**:
   - Storage account with 2 blob containers:
     - `batch-input`: Stores JSONL input files for batch jobs
     - `batch-output`: Stores results from Azure OpenAI batch jobs
   - Lifecycle policy: Automatically deletes files after 90 days
   - Security: HTTPS-only, TLS 1.2+, no public access

4. **Service Principal**:
   - Azure AD application and service principal for authentication
   - Client ID and secret for programmatic access
   - Valid for 1 year (renewable)

5. **RBAC Role Assignments**:
   - **Storage Blob Data Contributor**: Allows the service principal to read/write blob storage
   - **Cognitive Services OpenAI User**: Allows the service principal to use Azure OpenAI

## Prerequisites

1. **Azure CLI** installed and authenticated:
   ```bash
   brew install azure-cli  # macOS
   az login
   az account set --subscription "<your-subscription-id>"
   ```

2. **Pulumi CLI** installed:
   ```bash
   brew install pulumi  # macOS
   ```

3. **Node.js 18+** installed:
   ```bash
   brew install node  # macOS
   ```

4. **Azure OpenAI Access Approval**:
   - ⚠️ Azure OpenAI requires application approval
   - Apply at: https://aka.ms/oai/access
   - Typically takes 1-2 business days
   - You can deploy storage + service principal while waiting
   - Set `deployGpt4o: false` if not yet approved

## Setup

### 1. Install Dependencies

```bash
cd infra/azure/
npm install
```

### 2. Login to Pulumi

```bash
# Option A: Pulumi Cloud (recommended)
pulumi login

# Option B: Local file-based state
pulumi login --local
```

### 3. Initialize a New Stack

Create a stack for your environment:

```bash
pulumi stack init dev
```

### 4. Configure the Stack

Set required configuration values:

```bash
# Set Azure region (choose one close to your users)
pulumi config set azure-native:location southeastasia
# Options: southeastasia, eastus, westeurope, australiaeast, etc.

# Set environment name (optional, defaults to "dev")
pulumi config set environment dev

# Optional: Deploy GPT-4o for higher quality (default: false)
pulumi config set deployGpt4o true

# Optional: Skip GPT-4o-mini if you only want GPT-4o (default: true)
pulumi config set deployGpt4oMini false

# Optional: Set model capacities in thousands of TPM
pulumi config set gpt4oMiniCapacity 50  # Default: 50
pulumi config set gpt4oCapacity 20      # Default: 20
```

### 5. Preview and Deploy

```bash
pulumi preview
# or
npm run preview

pulumi up
# or
npm run up
```

## Post-Deployment

After deployment, retrieve the outputs:

```bash
# View all outputs
pulumi stack output

# Get specific values for .env file
pulumi stack output openaiEndpoint
pulumi stack output openaiApiKey --show-secrets
pulumi stack output gpt4oMiniDeploymentName
pulumi stack output gpt4oDeploymentName  # If you deployed GPT-4o
pulumi stack output storageAccountName
pulumi stack output storageConnectionString --show-secrets
pulumi stack output servicePrincipalClientId
pulumi stack output servicePrincipalTenantId
pulumi stack output servicePrincipalClientSecret --show-secrets
```

### Update Environment Variables

**Automatic (Recommended)**: Use the sync script from the infra root:

```bash
cd ..
./sync-env.sh --azure-only
# or for a specific stack:
./sync-env.sh --azure-only --azure-stack dev
```

**Manual**: Add these to your `.env` file in the repository root:

```bash
# Azure OpenAI
AZURE_OPENAI_ENDPOINT="$(pulumi stack output openaiEndpoint)"
AZURE_OPENAI_API_KEY="$(pulumi stack output openaiApiKey --show-secrets)"
AZURE_OPENAI_API_VERSION="2024-10-01-preview"
AZURE_OPENAI_GPT4O_MINI_DEPLOYMENT="$(pulumi stack output gpt4oMiniDeploymentName)"
AZURE_OPENAI_GPT4O_DEPLOYMENT="$(pulumi stack output gpt4oDeploymentName)"  # If deployed

# Azure Storage for batch processing
AZURE_STORAGE_ACCOUNT_NAME="$(pulumi stack output storageAccountName)"
AZURE_STORAGE_CONNECTION_STRING="$(pulumi stack output storageConnectionString --show-secrets)"
AZURE_BATCH_INPUT_CONTAINER="batch-input"
AZURE_BATCH_OUTPUT_CONTAINER="batch-output"

# Service Principal for authentication
AZURE_TENANT_ID="$(pulumi stack output servicePrincipalTenantId)"
AZURE_CLIENT_ID="$(pulumi stack output servicePrincipalClientId)"
AZURE_CLIENT_SECRET="$(pulumi stack output servicePrincipalClientSecret --show-secrets)"
```

## Authentication Options

The infrastructure supports two authentication methods:

### Option 1: Storage Account Key (Simpler)
```typescript
import { BlobServiceClient } from "@azure/storage-blob";

const connectionString = process.env.AZURE_STORAGE_CONNECTION_STRING;
const blobServiceClient = BlobServiceClient.fromConnectionString(connectionString);
```

### Option 2: Service Principal (More Secure, RBAC-based)
```typescript
import { ClientSecretCredential } from "@azure/identity";
import { BlobServiceClient } from "@azure/storage-blob";

const credential = new ClientSecretCredential(
    process.env.AZURE_TENANT_ID,
    process.env.AZURE_CLIENT_ID,
    process.env.AZURE_CLIENT_SECRET
);

const blobServiceClient = new BlobServiceClient(
    `https://${process.env.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net`,
    credential
);
```

## Azure OpenAI Batch API Usage

Once infrastructure is deployed, use the Azure OpenAI batch API:

```typescript
import { ClientSecretCredential } from "@azure/identity";
import { AzureOpenAI } from "openai";

// Authenticate with service principal
const credential = new ClientSecretCredential(
    process.env.AZURE_TENANT_ID!,
    process.env.AZURE_CLIENT_ID!,
    process.env.AZURE_CLIENT_SECRET!
);

// Get access token
const token = await credential.getToken("https://cognitiveservices.azure.com/.default");

// Create OpenAI client
const client = new AzureOpenAI({
    azureADTokenProvider: () => Promise.resolve(token.token),
    endpoint: process.env.AZURE_OPENAI_ENDPOINT,
    apiVersion: "2024-10-01-preview",
});

// Create batch job
const batchJob = await client.batches.create({
    input_file_id: "file-abc123",
    endpoint: "/chat/completions",
    completion_window: "24h",
});
```

## Managing Multiple Environments

Create separate stacks for different environments:

```bash
pulumi stack init dev
pulumi config set environment dev
pulumi up

pulumi stack init staging
pulumi config set environment staging
pulumi up

pulumi stack init production
pulumi config set environment production
pulumi up
```

## Destroying Resources

To destroy all resources:

```bash
pulumi destroy
# or
npm run destroy
```

## Development

Build TypeScript:

```bash
npm run build
```

## Cost Considerations

- **Storage Account**: ~$0.02/GB/month (LRS)
- **Storage Transactions**: ~$0.004/10,000 operations
- **Azure OpenAI**: Pay-per-token, batch API typically 50% cheaper than real-time
- **Service Principal**: Free
- **RBAC**: Free

Estimated monthly cost for low-moderate usage: $2-20

## Security Notes

1. **Service Principal**: Client secret is valid for 1 year. Rotate regularly.
2. **Storage Access**: Both containers have no public access
3. **TLS**: Enforced minimum TLS 1.2
4. **RBAC**: Principle of least privilege - only necessary permissions granted
5. **Secrets**: All sensitive outputs are marked as Pulumi secrets

## Troubleshooting

### TypeScript compilation errors

```bash
npm run build
```

### Azure AD permissions error

Ensure your Azure account has permissions to create service principals:
```bash
az ad sp list --show-mine
```

### OpenAI resource not found

Make sure the OpenAI resource name and resource group are correct:
```bash
az cognitiveservices account show \
  --name your-openai-resource \
  --resource-group your-resource-group
```

### Batch API not available

Check if batch API is available in your region:
```bash
az cognitiveservices account list-skus \
  --name your-openai-resource \
  --resource-group your-resource-group
```

Not all Azure regions support the batch API yet. Check Azure documentation for availability.

## Next Steps

1. Update `batch/config/settings.py` to include Azure Storage settings
2. Create batch processing utilities in `batch/pipeline/` for Azure OpenAI
3. Test with small batch jobs before scaling
4. Set up monitoring with Azure Monitor/Application Insights (optional)
