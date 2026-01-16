/**
 * AWS Infrastructure for Legal-AI Bedrock Batch Processing
 * 
 * This Pulumi program creates:
 * - S3 buckets for Bedrock batch input/output
 * - IAM role and policies for Bedrock batch jobs
 * - IAM user for application access
 */

import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";

// Configuration
const config = new pulumi.Config();
const environment = config.get("environment") || "dev";
const projectName = "legal-ai";
// We keep all Bedrock resources and S3 buckets in us-east-1 so batch jobs
// can run against Bedrock models that are only available in that region.
const bedrockRegion = "us-east-1";

// Common tags
const commonTags = {
    Project: projectName,
    Environment: environment,
    ManagedBy: "Pulumi",
};

// Get current AWS account info
const current = aws.getCallerIdentity({});

// S3 Bucket for batch job inputs
// Use a region suffix in the bucket name to avoid clashes with any existing
// buckets that might have been created in other regions.
const inputBucket = new aws.s3.BucketV2(`${projectName}-bedrock-batch-input-${environment}`, {
    bucket: `${projectName}-bedrock-batch-input-${environment}-${bedrockRegion}`,
    tags: commonTags,
});

// Block public access for input bucket
const inputBucketPublicAccessBlock = new aws.s3.BucketPublicAccessBlock(`${projectName}-input-public-access-block`, {
    bucket: inputBucket.id,
    blockPublicAcls: true,
    blockPublicPolicy: true,
    ignorePublicAcls: true,
    restrictPublicBuckets: true,
});

// S3 Bucket for batch job outputs
// Use a region suffix in the bucket name to avoid clashes with any existing
// buckets that might have been created in other regions.
const outputBucket = new aws.s3.BucketV2(`${projectName}-bedrock-batch-output-${environment}`, {
    bucket: `${projectName}-bedrock-batch-output-${environment}-${bedrockRegion}`,
    tags: commonTags,
});

// Block public access for output bucket
const outputBucketPublicAccessBlock = new aws.s3.BucketPublicAccessBlock(`${projectName}-output-public-access-block`, {
    bucket: outputBucket.id,
    blockPublicAcls: true,
    blockPublicPolicy: true,
    ignorePublicAcls: true,
    restrictPublicBuckets: true,
});

// Lifecycle policy for input bucket (delete after 90 days)
const inputBucketLifecycle = new aws.s3.BucketLifecycleConfigurationV2(`${projectName}-input-lifecycle`, {
    bucket: inputBucket.id,
    rules: [{
        id: "delete-old-inputs",
        status: "Enabled",
        expiration: {
            days: 90,
        },
    }],
});

// Lifecycle policy for output bucket (delete after 90 days)
const outputBucketLifecycle = new aws.s3.BucketLifecycleConfigurationV2(`${projectName}-output-lifecycle`, {
    bucket: outputBucket.id,
    rules: [{
        id: "delete-old-outputs",
        status: "Enabled",
        expiration: {
            days: 90,
        },
    }],
});

// IAM role for Bedrock batch processing
const bedrockRole = new aws.iam.Role(`${projectName}-bedrock-batch-role`, {
    name: `${projectName}-bedrock-batch-role-${environment}`,
    assumeRolePolicy: current.then(current => JSON.stringify({
        Version: "2012-10-17",
        Statement: [{
            Effect: "Allow",
            Principal: {
                Service: "bedrock.amazonaws.com",
            },
            Action: "sts:AssumeRole",
            Condition: {
                StringEquals: {
                    "aws:SourceAccount": current.accountId,
                },
            },
        }],
    })),
    tags: commonTags,
});

// IAM policy for S3 access (read input, write output)
const s3Policy = new aws.iam.RolePolicy(`${projectName}-bedrock-s3-policy`, {
    role: bedrockRole.id,
    policy: pulumi.all([inputBucket.arn, outputBucket.arn]).apply(([inputArn, outputArn]) =>
        JSON.stringify({
            Version: "2012-10-17",
            Statement: [
                {
                    Effect: "Allow",
                    Action: [
                        "s3:GetObject",
                        "s3:ListBucket",
                    ],
                    Resource: [
                        inputArn,
                        `${inputArn}/*`,
                    ],
                },
                {
                    Effect: "Allow",
                    Action: [
                        "s3:PutObject",
                        "s3:PutObjectAcl",
                    ],
                    Resource: [
                        `${outputArn}/*`,
                    ],
                },
            ],
        })
    ),
});

// IAM policy for invoking Bedrock models
const bedrockPolicy = new aws.iam.RolePolicy(`${projectName}-bedrock-invoke-policy`, {
    role: bedrockRole.id,
    policy: JSON.stringify({
        Version: "2012-10-17",
        Statement: [{
            Effect: "Allow",
            Action: [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
            ],
            Resource: [
                // Claude models (text generation)
                "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-opus-4-5:0",
                "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-7-sonnet:0",
                "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0",
                // Embedding models
                "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0",
                "arn:aws:bedrock:us-east-1::foundation-model/cohere.embed-english-v3",
                "arn:aws:bedrock:us-east-1::foundation-model/cohere.embed-multilingual-v3",
            ],
        }],
    }),
});

// IAM user for application access
const appUser = new aws.iam.User(`${projectName}-bedrock-app-user`, {
    name: `${projectName}-bedrock-app-user-${environment}`,
    tags: commonTags,
});

// IAM policy for the application user
const appUserPolicy = new aws.iam.UserPolicy(`${projectName}-app-user-policy`, {
    user: appUser.name,
    policy: pulumi.all([inputBucket.arn, outputBucket.arn, bedrockRole.arn]).apply(
        ([inputArn, outputArn, roleArn]) =>
            JSON.stringify({
                Version: "2012-10-17",
                Statement: [
                    {
                        Effect: "Allow",
                        Action: [
                            "s3:PutObject",
                            "s3:GetObject",
                            "s3:ListBucket",
                        ],
                        Resource: [
                            inputArn,
                            `${inputArn}/*`,
                            outputArn,
                            `${outputArn}/*`,
                        ],
                    },
                    {
                        Effect: "Allow",
                        Action: [
                            "bedrock:CreateModelInvocationJob",
                            "bedrock:GetModelInvocationJob",
                            "bedrock:ListModelInvocationJobs",
                            "bedrock:StopModelInvocationJob",
                            "bedrock:ListFoundationModels",
                            "bedrock:InvokeModel"
                        ],
                        Resource: "*",
                    },
                    {
                        Effect: "Allow",
                        Action: "iam:PassRole",
                        Resource: roleArn,
                        Condition: {
                            StringEquals: {
                                "iam:PassedToService": "bedrock.amazonaws.com",
                            },
                        },
                    },
                ],
            })
    ),
});

// Create access key for the application user
const appUserAccessKey = new aws.iam.AccessKey(`${projectName}-app-user-key`, {
    user: appUser.name,
});

// Exports
export const inputBucketName = inputBucket.bucket;
export const inputBucketArn = inputBucket.arn;
export const outputBucketName = outputBucket.bucket;
export const outputBucketArn = outputBucket.arn;
export const bedrockRoleArn = bedrockRole.arn;
export const appUserName = appUser.name;
export const appUserAccessKeyId = appUserAccessKey.id;
export const appUserSecretAccessKey = pulumi.secret(appUserAccessKey.secret);
