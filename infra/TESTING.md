# Infrastructure Testing Guide

This document describes how to run tests for the Legal-AI infrastructure code, including Pulumi programs and the sync-env.sh script.

## Overview

The infrastructure testing suite includes:

1. **AWS Pulumi Tests** - Unit tests for AWS infrastructure exports
2. **Azure Pulumi Tests** - Unit tests for Azure infrastructure exports
3. **sync-env.sh Tests** - Bash tests for the environment synchronization script

## Prerequisites

### For Pulumi Tests (AWS & Azure)

- Node.js 18+
- npm or yarn
- Pulumi CLI (not required for unit tests, but useful for development)

### For sync-env.sh Tests

- Bash
- BATS (Bash Automated Testing System)

Install BATS on macOS:
```bash
brew install bats-core
```

Install BATS on Linux:
```bash
# Ubuntu/Debian
sudo apt-get install bats

# Or install from source
git clone https://github.com/bats-core/bats-core.git
cd bats-core
sudo ./install.sh /usr/local
```

## Running Tests

### AWS Infrastructure Tests

Navigate to the AWS infrastructure directory and run tests:

```bash
cd infra/aws

# Install dependencies (first time only)
npm install

# Run tests
npm test

# Run tests in watch mode (re-runs on file changes)
npm run test:watch
```

**What's tested:**
- S3 bucket names and ARNs are exported correctly
- IAM role ARN is exported correctly
- IAM user name, access key ID, and secret access key are exported
- Resource naming consistency across environment

**Test file:** `infra/aws/index.test.ts`

### Azure Infrastructure Tests

Navigate to the Azure infrastructure directory and run tests:

```bash
cd infra/azure

# Install dependencies (first time only)
npm install

# Run tests
npm test

# Run tests in watch mode
npm run test:watch
```

**What's tested:**
- Resource group name is exported correctly
- Storage account name, ID, key, and connection string are exported
- Blob container names and URLs are exported correctly
- Service principal credentials (client ID, tenant ID, client secret, object ID) are exported
- Resource naming consistency across environment

**Test file:** `infra/azure/index.test.ts`

### sync-env.sh Script Tests

Navigate to the infrastructure root directory and run tests:

```bash
cd infra

# Run all BATS tests
bats sync-env.test.bats

# Run specific test by pattern
bats sync-env.test.bats --filter "AWS"

# Run with verbose output
bats sync-env.test.bats --verbose
```

**What's tested:**
- Creates .env file if it doesn't exist
- Updates existing AWS environment variables
- Adds new AWS environment variables
- Updates existing Azure environment variables
- Skips null or empty values
- Handles special characters in values
- Preserves unrelated environment variables
- Handles AWS-only and Azure-only modes
- Validates AWS and Azure directories exist
- Sets AWS_REGION default if not present
- Doesn't override existing AWS_REGION
- Accepts custom output file path
- Handles missing Pulumi stacks gracefully
- Handles missing Pulumi outputs gracefully

**Test file:** `infra/sync-env.test.bats`

## Test Architecture

### Pulumi Unit Tests

The Pulumi tests use **mocked runtime** instead of actual cloud resources. This means:

- Tests run quickly (no network calls)
- No cloud credentials required
- No cloud resources are created or billed
- Tests can run in CI/CD pipelines

The mocking is done via `pulumi.runtime.setMocks()`, which intercepts resource creation and provides fake responses.

**Testing Strategy:**
1. Mock the Pulumi runtime before importing infrastructure code
2. Import the infrastructure module (which triggers resource creation with mocks)
3. Resolve exported outputs using `.promise()` or `pulumi.unsecret()`
4. Assert that outputs match expected patterns and formats

**Example:**
```typescript
// Mock Pulumi runtime
pulumi.runtime.setMocks({
    newResource: (args) => {
        // Return mock resource state
        return { id: "mock-id", state: { ... } };
    },
    call: (args) => {
        // Return mock function call results
        return { outputs: { ... } };
    },
});

// Import infrastructure code (uses mocks)
import * as infra from "./index";

// Test exports
const bucketName = await infra.inputBucketName.promise();
expect(bucketName).to.match(/^legal-ai-bedrock-batch-input-/);
```

### sync-env.sh Tests

The sync-env.sh tests use **BATS** (Bash Automated Testing System), which provides:

- Test isolation (setup/teardown for each test)
- Assertions via standard bash commands
- Mocking support for external commands
- Parallel test execution

**Testing Strategy:**
1. Create temporary test environment in `setup()`
2. Mock Pulumi CLI commands to return test data
3. Test individual functions and behaviors
4. Clean up temporary files in `teardown()`

**Example:**
```bash
@test "sync-env.sh updates existing AWS environment variables" {
    # Create test .env file
    cat > "$TEST_ENV_FILE" << EOF
AWS_ACCESS_KEY_ID=OLD_KEY_ID
EOF

    # Run update logic
    sed -i '' "s|^AWS_ACCESS_KEY_ID=.*|AWS_ACCESS_KEY_ID=NEW_KEY_ID|" "$TEST_ENV_FILE"
    
    # Verify update
    grep -q "AWS_ACCESS_KEY_ID=NEW_KEY_ID" "$TEST_ENV_FILE"
}
```

## Continuous Integration

To run all tests in CI/CD:

```bash
# Install dependencies
cd infra/aws && npm install && cd ..
cd infra/azure && npm install && cd ..

# Run all tests
npm test --prefix aws
npm test --prefix azure
bats sync-env.test.bats
```

### GitHub Actions Example

```yaml
name: Infrastructure Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'
      
      - name: Install BATS
        run: |
          sudo apt-get update
          sudo apt-get install -y bats
      
      - name: Run AWS tests
        run: |
          cd infra/aws
          npm install
          npm test
      
      - name: Run Azure tests
        run: |
          cd infra/azure
          npm install
          npm test
      
      - name: Run sync-env.sh tests
        run: |
          cd infra
          bats sync-env.test.bats
```

## Writing New Tests

### Adding Pulumi Tests

1. Add new test cases to the appropriate `describe` block in `index.test.ts`
2. Use the existing mock setup (it's configured before the `import`)
3. Resolve outputs using `.promise()` or `pulumi.unsecret()` for secrets
4. Use Chai assertions to verify behavior

**Example:**
```typescript
describe("New Resource", () => {
    it("should export resource name correctly", async () => {
        const resourceName = await infra.myResourceName.promise();
        expect(resourceName).to.be.a("string");
        expect(resourceName).to.match(/^expected-pattern/);
    });
});
```

### Adding sync-env.sh Tests

1. Add new `@test` blocks to `sync-env.test.bats`
2. Use `setup()` and `teardown()` for test isolation
3. Create test files in `$TEST_DIR` (automatically cleaned up)
4. Use standard bash commands for assertions

**Example:**
```bash
@test "sync-env.sh handles new scenario" {
    # Arrange
    cat > "$TEST_ENV_FILE" << EOF
EXISTING_VAR=value
EOF

    # Act
    echo "NEW_VAR=new-value" >> "$TEST_ENV_FILE"
    
    # Assert
    grep -q "NEW_VAR=new-value" "$TEST_ENV_FILE"
    grep -q "EXISTING_VAR=value" "$TEST_ENV_FILE"
}
```

## Troubleshooting

### Pulumi Tests Failing

**Issue:** `Error: Cannot find module '@pulumi/pulumi'`
- **Solution:** Run `npm install` in the aws/ or azure/ directory

**Issue:** `TypeError: Cannot read property 'promise' of undefined`
- **Solution:** Ensure mocks are set up before importing infrastructure code

**Issue:** Tests pass locally but fail in CI
- **Solution:** Check Node.js version consistency, ensure all dependencies are in package.json

### BATS Tests Failing

**Issue:** `bats: command not found`
- **Solution:** Install BATS using `brew install bats-core` (macOS) or `apt-get install bats` (Linux)

**Issue:** `sed: illegal option` on Linux
- **Solution:** Remove the `''` after `sed -i` (macOS requires it, Linux doesn't)

**Issue:** Tests create files in unexpected locations
- **Solution:** Check that `$TEST_DIR` is properly set in `setup()`

## Coverage Goals

- **AWS Infrastructure:** ✅ All exports tested
- **Azure Infrastructure:** ✅ All exports tested  
- **sync-env.sh:** ✅ Core functionality tested (update, add, skip, error handling)

## Future Improvements

- [ ] Add integration tests that deploy to test cloud accounts
- [ ] Add performance tests for large-scale deployments
- [ ] Add security scanning for infrastructure code
- [ ] Add snapshot testing for Pulumi program outputs
- [ ] Add tests for Pulumi stack configuration validation
