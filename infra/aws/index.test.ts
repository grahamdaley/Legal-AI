/**
 * Unit tests for AWS Pulumi infrastructure
 * Tests that resource names and ARNs are exported correctly
 */

import * as pulumi from "@pulumi/pulumi";
import { describe, it, before } from "mocha";
import { expect } from "chai";

// Mock Pulumi runtime for testing
pulumi.runtime.setMocks({
    newResource: function(args: pulumi.runtime.MockResourceArgs): {id: string, state: any} {
        const resourceType = args.type;
        const resourceName = args.name;
        
        // Mock S3 buckets
        if (resourceType === "aws:s3/bucketV2:BucketV2") {
            const bucketName = args.inputs.bucket || `${resourceName}-bucket`;
            return {
                id: bucketName,
                state: {
                    ...args.inputs,
                    bucket: bucketName,
                    arn: `arn:aws:s3:::${bucketName}`,
                },
            };
        }
        
        // Mock IAM Role
        if (resourceType === "aws:iam/role:Role") {
            const roleName = args.inputs.name || resourceName;
            return {
                id: roleName,
                state: {
                    ...args.inputs,
                    name: roleName,
                    arn: `arn:aws:iam::123456789012:role/${roleName}`,
                },
            };
        }
        
        // Mock IAM User
        if (resourceType === "aws:iam/user:User") {
            const userName = args.inputs.name || resourceName;
            return {
                id: userName,
                state: {
                    ...args.inputs,
                    name: userName,
                    arn: `arn:aws:iam::123456789012:user/${userName}`,
                },
            };
        }
        
        // Mock IAM Access Key
        if (resourceType === "aws:iam/accessKey:AccessKey") {
            return {
                id: "AKIAIOSFODNN7EXAMPLE",
                state: {
                    ...args.inputs,
                    id: "AKIAIOSFODNN7EXAMPLE",
                    secret: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
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
        // Mock AWS caller identity
        if (args.token === "aws:index/getCallerIdentity:getCallerIdentity") {
            return {
                outputs: {
                    accountId: "123456789012",
                    arn: "arn:aws:iam::123456789012:user/test-user",
                    userId: "AIDAI1234567890EXAMPLE",
                },
            };
        }
        return {outputs: {}};
    },
});

// Import the infrastructure code after setting up mocks
import * as infra from "./index";

describe("AWS Infrastructure Exports", () => {

    describe("S3 Input Bucket", () => {
        it("should export input bucket name", async () => {
            const bucketName = await new Promise<string>((resolve) => {
                infra.inputBucketName.apply(v => { resolve(v); return v; });
            });
            expect(bucketName).to.be.a("string");
            expect(bucketName).to.match(/^legal-ai-bedrock-batch-input-/);
        });

        it("should export input bucket ARN", async () => {
            const bucketArn = await new Promise<string>((resolve) => {
                infra.inputBucketArn.apply(v => { resolve(v); return v; });
            });
            expect(bucketArn).to.be.a("string");
            expect(bucketArn).to.match(/^arn:aws:s3:::/);
            expect(bucketArn).to.include("legal-ai-bedrock-batch-input-");
        });

        it("should have matching bucket name in ARN", async () => {
            const bucketName = await new Promise<string>((resolve) => {
                infra.inputBucketName.apply(v => { resolve(v); return v; });
            });
            const bucketArn = await new Promise<string>((resolve) => {
                infra.inputBucketArn.apply(v => { resolve(v); return v; });
            });
            expect(bucketArn).to.include(bucketName);
        });
    });

    describe("S3 Output Bucket", () => {
        it("should export output bucket name", async () => {
            const bucketName = await new Promise<string>((resolve) => {
                infra.outputBucketName.apply(v => { resolve(v); return v; });
            });
            expect(bucketName).to.be.a("string");
            expect(bucketName).to.match(/^legal-ai-bedrock-batch-output-/);
        });

        it("should export output bucket ARN", async () => {
            const bucketArn = await new Promise<string>((resolve) => {
                infra.outputBucketArn.apply(v => { resolve(v); return v; });
            });
            expect(bucketArn).to.be.a("string");
            expect(bucketArn).to.match(/^arn:aws:s3:::/);
            expect(bucketArn).to.include("legal-ai-bedrock-batch-output-");
        });

        it("should have matching bucket name in ARN", async () => {
            const bucketName = await new Promise<string>((resolve) => {
                infra.outputBucketName.apply(v => { resolve(v); return v; });
            });
            const bucketArn = await new Promise<string>((resolve) => {
                infra.outputBucketArn.apply(v => { resolve(v); return v; });
            });
            expect(bucketArn).to.include(bucketName);
        });
    });

    describe("IAM Bedrock Role", () => {
        it("should export bedrock role ARN", async () => {
            const roleArn = await new Promise<string>((resolve) => {
                infra.bedrockRoleArn.apply(v => { resolve(v); return v; });
            });
            expect(roleArn).to.be.a("string");
            expect(roleArn).to.match(/^arn:aws:iam::\d{12}:role\//);
            expect(roleArn).to.include("legal-ai-bedrock-batch-role-");
        });
    });

    describe("IAM Application User", () => {
        it("should export app user name", async () => {
            const userName = await new Promise<string>((resolve) => {
                infra.appUserName.apply(v => { resolve(v); return v; });
            });
            expect(userName).to.be.a("string");
            expect(userName).to.match(/^legal-ai-bedrock-app-user-/);
        });

        it("should export app user access key ID", async () => {
            const accessKeyId = await new Promise<string>((resolve) => {
                infra.appUserAccessKeyId.apply(v => { resolve(v); return v; });
            });
            expect(accessKeyId).to.be.a("string");
            expect(accessKeyId).to.match(/^AKIA[A-Z0-9]{16}$/);
        });

        it("should export app user secret access key", async () => {
            const secretAccessKey = await new Promise<string>((resolve) => {
                infra.appUserSecretAccessKey.apply(v => {
                    if (pulumi.Output.isInstance(v)) {
                        v.apply(secret => { resolve(secret as string); return secret; });
                    } else {
                        resolve(v as string);
                    }
                    return v;
                });
            });
            expect(secretAccessKey).to.be.a("string");
            expect(secretAccessKey.length).to.be.at.least(20);
        });
    });

    describe("Resource Naming Consistency", () => {
        it("should use consistent environment naming across resources", async () => {
            const inputBucketName = await new Promise<string>((resolve) => {
                infra.inputBucketName.apply(v => { resolve(v); return v; });
            });
            const outputBucketName = await new Promise<string>((resolve) => {
                infra.outputBucketName.apply(v => { resolve(v); return v; });
            });
            const roleArn = await new Promise<string>((resolve) => {
                infra.bedrockRoleArn.apply(v => { resolve(v); return v; });
            });
            const userName = await new Promise<string>((resolve) => {
                infra.appUserName.apply(v => { resolve(v); return v; });
            });
            
            const environment = inputBucketName.split("-").pop();
            expect(outputBucketName).to.include(environment!);
            expect(roleArn).to.include(environment!);
            expect(userName).to.include(environment!);
        });
    });
});
