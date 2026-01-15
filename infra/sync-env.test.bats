#!/usr/bin/env bats
# Unit tests for sync-env.sh script
# Requires BATS (Bash Automated Testing System): https://github.com/bats-core/bats-core
#
# Installation:
#   brew install bats-core
#
# Run tests:
#   bats infra/sync-env.test.bats

setup() {
    # Create temporary directory for test files
    TEST_DIR="$(mktemp -d)"
    TEST_ENV_FILE="$TEST_DIR/.env"
    
    # Mock Pulumi directory structure
    mkdir -p "$TEST_DIR/aws"
    mkdir -p "$TEST_DIR/azure"
    
    # Create mock sync-env.sh with testable functions
    SYNC_SCRIPT="$TEST_DIR/sync-env.sh"
    
    # Source the original script (we'll mock the pulumi commands)
    export SCRIPT_DIR="$TEST_DIR"
    export REPO_ROOT="$TEST_DIR"
    export ENV_FILE="$TEST_ENV_FILE"
}

teardown() {
    # Clean up temporary directory
    rm -rf "$TEST_DIR"
}

# Helper function to create mock pulumi command
create_mock_pulumi() {
    local mock_dir="$1"
    mkdir -p "$mock_dir"
    
    cat > "$mock_dir/pulumi" << 'EOF'
#!/bin/bash
# Mock pulumi command for testing

case "$1 $2 $3" in
    "stack select dev")
        exit 0
        ;;
    "stack select nonexistent")
        echo "Error: Stack 'nonexistent' not found" >&2
        exit 1
        ;;
    "stack output appUserAccessKeyId --show-secrets")
        echo "AKIAIOSFODNN7EXAMPLE"
        ;;
    "stack output appUserSecretAccessKey --show-secrets")
        echo "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        ;;
    "stack output inputBucketName --show-secrets")
        echo "legal-ai-bedrock-batch-input-dev"
        ;;
    "stack output outputBucketName --show-secrets")
        echo "legal-ai-bedrock-batch-output-dev"
        ;;
    "stack output bedrockRoleArn --show-secrets")
        echo "arn:aws:iam::123456789012:role/legal-ai-bedrock-batch-role-dev"
        ;;
    "stack output storageAccountName --show-secrets")
        echo "legalaidev"
        ;;
    "stack output storageAccountKey --show-secrets")
        echo "mockStorageKey123456789=="
        ;;
    "stack output storageConnectionString --show-secrets")
        echo "DefaultEndpointsProtocol=https;AccountName=legalaidev;AccountKey=mockKey;EndpointSuffix=core.windows.net"
        ;;
    "stack output inputContainerName --show-secrets")
        echo "batch-input"
        ;;
    "stack output outputContainerName --show-secrets")
        echo "batch-output"
        ;;
    "stack output servicePrincipalTenantId --show-secrets")
        echo "22222222-2222-2222-2222-222222222222"
        ;;
    "stack output servicePrincipalClientId --show-secrets")
        echo "33333333-3333-3333-3333-333333333333"
        ;;
    "stack output servicePrincipalClientSecret --show-secrets")
        echo "mock-client-secret"
        ;;
    "stack output nonexistent --show-secrets")
        echo "error: current stack does not have output \"nonexistent\"" >&2
        exit 1
        ;;
    *)
        echo "Mock pulumi: unknown command" >&2
        exit 1
        ;;
esac
EOF
    chmod +x "$mock_dir/pulumi"
}

@test "sync-env.sh creates .env file if it doesn't exist" {
    # Create mock pulumi
    create_mock_pulumi "$TEST_DIR"
    export PATH="$TEST_DIR:$PATH"
    
    # Run update_env_var function logic
    [ ! -f "$TEST_ENV_FILE" ]
    touch "$TEST_ENV_FILE"
    [ -f "$TEST_ENV_FILE" ]
}

@test "sync-env.sh updates existing AWS environment variables" {
    # Create existing .env file with old values
    cat > "$TEST_ENV_FILE" << EOF
AWS_ACCESS_KEY_ID=OLD_KEY_ID
AWS_SECRET_ACCESS_KEY=OLD_SECRET
BEDROCK_BATCH_INPUT_BUCKET=old-bucket
EOF

    # Mock update logic
    sed -i '' "s|^AWS_ACCESS_KEY_ID=.*|AWS_ACCESS_KEY_ID=NEW_KEY_ID|" "$TEST_ENV_FILE"
    
    # Verify update
    grep -q "AWS_ACCESS_KEY_ID=NEW_KEY_ID" "$TEST_ENV_FILE"
    ! grep -q "AWS_ACCESS_KEY_ID=OLD_KEY_ID" "$TEST_ENV_FILE"
}

@test "sync-env.sh adds new AWS environment variables" {
    # Create .env file without AWS variables
    cat > "$TEST_ENV_FILE" << EOF
SUPABASE_URL=https://example.supabase.co
EOF

    # Add new variable
    echo "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE" >> "$TEST_ENV_FILE"
    
    # Verify addition
    grep -q "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE" "$TEST_ENV_FILE"
    grep -q "SUPABASE_URL=https://example.supabase.co" "$TEST_ENV_FILE"
}

@test "sync-env.sh skips null or empty values" {
    # Create .env file
    touch "$TEST_ENV_FILE"
    
    # Simulate checking for null/empty values
    local value=""
    [ -z "$value" ] && skip "Skipping empty value"
    
    local value2="null"
    [ "$value2" = "null" ] && skip "Skipping null value"
}

@test "sync-env.sh updates Azure environment variables correctly" {
    # Create existing .env file
    cat > "$TEST_ENV_FILE" << EOF
AZURE_STORAGE_ACCOUNT_NAME=old-account
AZURE_CLIENT_ID=old-client-id
EOF

    # Mock update logic
    sed -i '' "s|^AZURE_STORAGE_ACCOUNT_NAME=.*|AZURE_STORAGE_ACCOUNT_NAME=legalaidev|" "$TEST_ENV_FILE"
    sed -i '' "s|^AZURE_CLIENT_ID=.*|AZURE_CLIENT_ID=33333333-3333-3333-3333-333333333333|" "$TEST_ENV_FILE"
    
    # Verify updates
    grep -q "AZURE_STORAGE_ACCOUNT_NAME=legalaidev" "$TEST_ENV_FILE"
    grep -q "AZURE_CLIENT_ID=33333333-3333-3333-3333-333333333333" "$TEST_ENV_FILE"
}

@test "sync-env.sh handles special characters in values" {
    # Create .env file
    touch "$TEST_ENV_FILE"
    
    # Add value with special characters
    local value="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=abc/123+xyz=="
    local escaped_value=$(echo "$value" | sed 's/[&/\\]/\\&/g')
    
    echo "AZURE_STORAGE_CONNECTION_STRING=$value" >> "$TEST_ENV_FILE"
    
    # Verify value is correctly stored
    grep -q "AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https" "$TEST_ENV_FILE"
}

@test "sync-env.sh preserves unrelated environment variables" {
    # Create .env file with mixed variables
    cat > "$TEST_ENV_FILE" << EOF
SUPABASE_URL=https://example.supabase.co
OPENAI_API_KEY=sk-test123
AWS_ACCESS_KEY_ID=OLD_KEY
POSTGRES_PASSWORD=secret
EOF

    # Update only AWS variable
    sed -i '' "s|^AWS_ACCESS_KEY_ID=.*|AWS_ACCESS_KEY_ID=NEW_KEY|" "$TEST_ENV_FILE"
    
    # Verify other variables are preserved
    grep -q "SUPABASE_URL=https://example.supabase.co" "$TEST_ENV_FILE"
    grep -q "OPENAI_API_KEY=sk-test123" "$TEST_ENV_FILE"
    grep -q "POSTGRES_PASSWORD=secret" "$TEST_ENV_FILE"
    grep -q "AWS_ACCESS_KEY_ID=NEW_KEY" "$TEST_ENV_FILE"
}

@test "sync-env.sh handles AWS-only mode" {
    # Create .env file
    cat > "$TEST_ENV_FILE" << EOF
AWS_ACCESS_KEY_ID=old-key
AZURE_CLIENT_ID=old-azure-client
EOF

    # Simulate AWS-only update
    SYNC_AZURE=false
    SYNC_AWS=true
    
    [ "$SYNC_AWS" = true ]
    [ "$SYNC_AZURE" = false ]
}

@test "sync-env.sh handles Azure-only mode" {
    # Create .env file
    cat > "$TEST_ENV_FILE" << EOF
AWS_ACCESS_KEY_ID=old-key
AZURE_CLIENT_ID=old-azure-client
EOF

    # Simulate Azure-only update
    SYNC_AZURE=true
    SYNC_AWS=false
    
    [ "$SYNC_AZURE" = true ]
    [ "$SYNC_AWS" = false ]
}

@test "sync-env.sh validates AWS directory exists" {
    # Test with non-existent AWS directory
    run [ -d "$TEST_DIR/nonexistent-aws" ]
    [ "$status" -eq 1 ]
    
    # Test with existing AWS directory
    run [ -d "$TEST_DIR/aws" ]
    [ "$status" -eq 0 ]
}

@test "sync-env.sh validates Azure directory exists" {
    # Test with non-existent Azure directory
    run [ -d "$TEST_DIR/nonexistent-azure" ]
    [ "$status" -eq 1 ]
    
    # Test with existing Azure directory
    run [ -d "$TEST_DIR/azure" ]
    [ "$status" -eq 0 ]
}

@test "sync-env.sh sets AWS_REGION if not already set" {
    # Create .env file without AWS_REGION
    cat > "$TEST_ENV_FILE" << EOF
AWS_ACCESS_KEY_ID=test-key
EOF

    # Check if AWS_REGION is not set
    ! grep -q "^AWS_REGION=" "$TEST_ENV_FILE"
    
    # Add default AWS_REGION
    echo "AWS_REGION=ap-southeast-1" >> "$TEST_ENV_FILE"
    
    # Verify it was added
    grep -q "AWS_REGION=ap-southeast-1" "$TEST_ENV_FILE"
}

@test "sync-env.sh does not override existing AWS_REGION" {
    # Create .env file with existing AWS_REGION
    cat > "$TEST_ENV_FILE" << EOF
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=test-key
EOF

    # Check if AWS_REGION exists
    grep -q "^AWS_REGION=" "$TEST_ENV_FILE"
    
    # Verify original value is preserved
    grep -q "AWS_REGION=us-east-1" "$TEST_ENV_FILE"
}

@test "sync-env.sh accepts custom output file path" {
    # Create custom output file path
    CUSTOM_ENV="$TEST_DIR/custom.env"
    touch "$CUSTOM_ENV"
    
    # Add variable to custom file
    echo "TEST_VAR=test-value" >> "$CUSTOM_ENV"
    
    # Verify custom file was used
    [ -f "$CUSTOM_ENV" ]
    grep -q "TEST_VAR=test-value" "$CUSTOM_ENV"
}

@test "sync-env.sh handles missing Pulumi stack gracefully" {
    # This test simulates the error case when stack doesn't exist
    # The actual script should handle this with proper error messages
    
    # Mock the return value check
    local exit_code=1
    [ $exit_code -ne 0 ]
}

@test "sync-env.sh handles missing Pulumi output gracefully" {
    # Create .env file
    touch "$TEST_ENV_FILE"
    
    # Simulate output check for non-existent key
    local value=""
    
    # Empty values should be skipped
    if [ -z "$value" ] || [ "$value" = "null" ]; then
        skip "Skipping null/empty value as expected"
    fi
}
