#!/bin/bash
# Sync Pulumi stack outputs to .env file
# Usage: ./sync-env.sh [aws-stack-name] [azure-stack-name]

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$REPO_ROOT/.env"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

function print_usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --aws-stack NAME        Sync from AWS stack NAME (default: current stack)"
    echo "  --azure-stack NAME      Sync from Azure stack NAME (default: current stack)"
    echo "  --aws-only             Only sync AWS outputs"
    echo "  --azure-only           Only sync Azure outputs"
    echo "  --output FILE          Output to specific file (default: ../.env)"
    echo ""
    echo "Examples:"
    echo "  $0                                  # Sync both using current stacks"
    echo "  $0 --aws-stack dev                  # Sync AWS dev stack"
    echo "  $0 --azure-stack prod               # Sync Azure prod stack"
    echo "  $0 --aws-only --aws-stack staging   # Only sync AWS staging"
    exit 1
}

# Parse arguments
SYNC_AWS=true
SYNC_AZURE=true
AWS_STACK=""
AZURE_STACK=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --aws-stack)
            AWS_STACK="$2"
            shift 2
            ;;
        --azure-stack)
            AZURE_STACK="$2"
            shift 2
            ;;
        --aws-only)
            SYNC_AZURE=false
            shift
            ;;
        --azure-only)
            SYNC_AWS=false
            shift
            ;;
        --output)
            ENV_FILE="$2"
            shift 2
            ;;
        --help|-h)
            print_usage
            ;;
        *)
            echo "Unknown option: $1"
            print_usage
            ;;
    esac
done

echo -e "${BLUE}Syncing Pulumi stack outputs to .env file${NC}"
echo ""

# Function to get Pulumi output
get_pulumi_output() {
    local dir=$1
    local key=$2
    local stack=$3
    
    cd "$dir"
    if [ -n "$stack" ]; then
        pulumi stack select "$stack" 2>/dev/null || {
            echo -e "${RED}Error: Stack '$stack' not found in $dir${NC}"
            return 1
        }
    fi
    
    # Check if we need --show-secrets flag
    local value=$(pulumi stack output "$key" --show-secrets 2>/dev/null)
    if [ $? -ne 0 ]; then
        value=$(pulumi stack output "$key" 2>/dev/null)
    fi
    
    echo "$value"
}

# Function to update or add env var
update_env_var() {
    local key=$1
    local value=$2
    
    if [ -z "$value" ] || [ "$value" = "null" ]; then
        echo -e "${YELLOW}  ⚠ Skipping $key (no value)${NC}"
        return
    fi
    
    # Escape special characters for sed
    local escaped_value=$(echo "$value" | sed 's/[&/\]/\\&/g')
    
    if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        # Update existing value
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^${key}=.*|${key}=${escaped_value}|" "$ENV_FILE"
        else
            sed -i "s|^${key}=.*|${key}=${escaped_value}|" "$ENV_FILE"
        fi
        echo -e "${GREEN}  ✓ Updated $key${NC}"
    else
        # Add new value
        echo "${key}=${value}" >> "$ENV_FILE"
        echo -e "${GREEN}  ✓ Added $key${NC}"
    fi
}

# Create .env if it doesn't exist
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}Creating new .env file at $ENV_FILE${NC}"
    touch "$ENV_FILE"
fi

# Sync AWS outputs
if [ "$SYNC_AWS" = true ]; then
    echo -e "${BLUE}Syncing AWS outputs...${NC}"
    
    AWS_DIR="$SCRIPT_DIR/aws"
    if [ ! -d "$AWS_DIR" ]; then
        echo -e "${RED}Error: AWS directory not found at $AWS_DIR${NC}"
        exit 1
    fi
    
    # Get AWS outputs
    AWS_ACCESS_KEY_ID=$(get_pulumi_output "$AWS_DIR" "appUserAccessKeyId" "$AWS_STACK")
    AWS_SECRET_ACCESS_KEY=$(get_pulumi_output "$AWS_DIR" "appUserSecretAccessKey" "$AWS_STACK")
    BEDROCK_BATCH_INPUT_BUCKET=$(get_pulumi_output "$AWS_DIR" "inputBucketName" "$AWS_STACK")
    BEDROCK_BATCH_OUTPUT_BUCKET=$(get_pulumi_output "$AWS_DIR" "outputBucketName" "$AWS_STACK")
    BEDROCK_BATCH_ROLE_ARN=$(get_pulumi_output "$AWS_DIR" "bedrockRoleArn" "$AWS_STACK")
    
    # Update .env
    update_env_var "AWS_ACCESS_KEY_ID" "$AWS_ACCESS_KEY_ID"
    update_env_var "AWS_SECRET_ACCESS_KEY" "$AWS_SECRET_ACCESS_KEY"
    update_env_var "BEDROCK_BATCH_INPUT_BUCKET" "$BEDROCK_BATCH_INPUT_BUCKET"
    update_env_var "BEDROCK_BATCH_OUTPUT_BUCKET" "$BEDROCK_BATCH_OUTPUT_BUCKET"
    update_env_var "BEDROCK_BATCH_ROLE_ARN" "$BEDROCK_BATCH_ROLE_ARN"
    
    # Set AWS_REGION if not already set
    if ! grep -q "^AWS_REGION=" "$ENV_FILE" 2>/dev/null; then
        update_env_var "AWS_REGION" "us-east-1"
    fi
    
    echo ""
fi

# Sync Azure outputs
if [ "$SYNC_AZURE" = true ]; then
    echo -e "${BLUE}Syncing Azure outputs...${NC}"
    
    AZURE_DIR="$SCRIPT_DIR/azure"
    if [ ! -d "$AZURE_DIR" ]; then
        echo -e "${RED}Error: Azure directory not found at $AZURE_DIR${NC}"
        exit 1
    fi
    
    # Get Azure outputs
    AZURE_OPENAI_ENDPOINT=$(get_pulumi_output "$AZURE_DIR" "openaiEndpoint" "$AZURE_STACK")
    AZURE_OPENAI_API_KEY=$(get_pulumi_output "$AZURE_DIR" "openaiApiKey" "$AZURE_STACK")
    AZURE_OPENAI_GPT4O_MINI_DEPLOYMENT=$(get_pulumi_output "$AZURE_DIR" "gpt4oMiniDeploymentName" "$AZURE_STACK")
    AZURE_OPENAI_GPT4O_DEPLOYMENT=$(get_pulumi_output "$AZURE_DIR" "gpt4oDeploymentName" "$AZURE_STACK")
    AZURE_STORAGE_ACCOUNT_NAME=$(get_pulumi_output "$AZURE_DIR" "storageAccountName" "$AZURE_STACK")
    AZURE_STORAGE_ACCOUNT_KEY=$(get_pulumi_output "$AZURE_DIR" "storageAccountKey" "$AZURE_STACK")
    AZURE_STORAGE_CONNECTION_STRING=$(get_pulumi_output "$AZURE_DIR" "storageConnectionString" "$AZURE_STACK")
    AZURE_BATCH_INPUT_CONTAINER=$(get_pulumi_output "$AZURE_DIR" "inputContainerName" "$AZURE_STACK")
    AZURE_BATCH_OUTPUT_CONTAINER=$(get_pulumi_output "$AZURE_DIR" "outputContainerName" "$AZURE_STACK")
    AZURE_TENANT_ID=$(get_pulumi_output "$AZURE_DIR" "servicePrincipalTenantId" "$AZURE_STACK")
    AZURE_CLIENT_ID=$(get_pulumi_output "$AZURE_DIR" "servicePrincipalClientId" "$AZURE_STACK")
    AZURE_CLIENT_SECRET=$(get_pulumi_output "$AZURE_DIR" "servicePrincipalClientSecret" "$AZURE_STACK")
    
    # Update .env
    update_env_var "AZURE_OPENAI_ENDPOINT" "$AZURE_OPENAI_ENDPOINT"
    update_env_var "AZURE_OPENAI_API_KEY" "$AZURE_OPENAI_API_KEY"
    update_env_var "AZURE_OPENAI_GPT4O_MINI_DEPLOYMENT" "$AZURE_OPENAI_GPT4O_MINI_DEPLOYMENT"
    update_env_var "AZURE_OPENAI_GPT4O_DEPLOYMENT" "$AZURE_OPENAI_GPT4O_DEPLOYMENT"
    update_env_var "AZURE_STORAGE_ACCOUNT_NAME" "$AZURE_STORAGE_ACCOUNT_NAME"
    update_env_var "AZURE_STORAGE_ACCOUNT_KEY" "$AZURE_STORAGE_ACCOUNT_KEY"
    update_env_var "AZURE_STORAGE_CONNECTION_STRING" "$AZURE_STORAGE_CONNECTION_STRING"
    update_env_var "AZURE_BATCH_INPUT_CONTAINER" "$AZURE_BATCH_INPUT_CONTAINER"
    update_env_var "AZURE_BATCH_OUTPUT_CONTAINER" "$AZURE_BATCH_OUTPUT_CONTAINER"
    update_env_var "AZURE_TENANT_ID" "$AZURE_TENANT_ID"
    update_env_var "AZURE_CLIENT_ID" "$AZURE_CLIENT_ID"
    update_env_var "AZURE_CLIENT_SECRET" "$AZURE_CLIENT_SECRET"
    
    # Set API version if not already set
    if ! grep -q "^AZURE_OPENAI_API_VERSION=" "$ENV_FILE" 2>/dev/null; then
        update_env_var "AZURE_OPENAI_API_VERSION" "2024-10-01-preview"
    fi
    
    echo ""
fi

echo -e "${GREEN}✓ Successfully synced Pulumi outputs to $ENV_FILE${NC}"
echo ""
echo -e "${YELLOW}Note: Other environment variables (like SUPABASE_*) must be set manually${NC}"
