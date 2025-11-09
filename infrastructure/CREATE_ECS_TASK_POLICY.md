# Create ECS Task Policy - Step by Step Guide

## Overview

The `MLPlatformECSTaskPolicy` doesn't exist yet. This guide will help you create it with all the necessary permissions for the ECS Task Role.

## Step 1: Create the Policy via AWS Console

1. **Go to IAM Console**

   - Open: https://console.aws.amazon.com/iam/
   - Click on **Policies** in the left menu

2. **Create New Policy**

   - Click the **Create policy** button
   - Click on the **JSON** tab

3. **Copy Policy Document**

   - Open the file: `infrastructure/MLPlatformECSTaskPolicy.json`
   - Copy the entire contents
   - Paste it into the JSON editor in AWS Console

4. **Review and Create**
   - Click **Next**
   - Policy name: `MLPlatformECSTaskPolicy`
   - Description: `Policy for ECS Task Role to access S3, DynamoDB, and CloudWatch Logs`
   - Click **Create policy**

## Step 2: Attach Policy to Role

1. **Go to Roles**

   - Click on **Roles** in the left menu
   - Search for `MLPlatformECSTaskRole`
   - Click on the role

2. **Attach Policy**
   - Click on the **Add permissions** dropdown
   - Select **Attach policies**
   - Search for `MLPlatformECSTaskPolicy`
   - Check the box next to it
   - Click **Add permissions**

## Step 3: Verify

After creating and attaching the policy, verify it works:

```bash
# Run the test
pytest tests/test_ecs_task_dynamodb_permissions.py -v

# Or check manually (if you have permissions)
aws iam list-attached-role-policies --role-name MLPlatformECSTaskRole
```

## Policy Details

This policy grants the ECS Task Role the following permissions:

### S3 Permissions

- `s3:GetObject` - Download training data
- `s3:PutObject` - Upload model artifacts
- `s3:ListBucket` - List bucket contents

### DynamoDB Permissions (ALL 6 REQUIRED)

- `dynamodb:GetItem` - Get job details
- `dynamodb:PutItem` - Create job entries
- `dynamodb:UpdateItem` - Update job status (CRITICAL)
- `dynamodb:Scan` - List all jobs
- `dynamodb:Query` - Query jobs by attributes
- `dynamodb:DescribeTable` - Get table metadata

### CloudWatch Logs Permissions

- `logs:CreateLogGroup` - Create log groups
- `logs:CreateLogStream` - Create log streams
- `logs:PutLogEvents` - Write log events

## Alternative: Create via AWS CLI (Requires Admin)

If you have admin permissions, you can create it via CLI:

```bash
cd infrastructure
aws iam create-policy \
    --policy-name MLPlatformECSTaskPolicy \
    --policy-document file://MLPlatformECSTaskPolicy.json \
    --description "Policy for ECS Task Role to access S3, DynamoDB, and CloudWatch Logs"

# Attach to role
aws iam attach-role-policy \
    --role-name MLPlatformECSTaskRole \
    --policy-arn arn:aws:iam::618574523116:policy/MLPlatformECSTaskPolicy
```

## Troubleshooting

### Policy already exists

If you get an error that the policy already exists:

1. Go to IAM → Policies
2. Search for `MLPlatformECSTaskPolicy`
3. Edit the policy
4. Update the DynamoDB section to include all 6 permissions

### Role doesn't exist

If `MLPlatformECSTaskRole` doesn't exist, create it first:

1. Go to IAM → Roles → Create role
2. Select **AWS service** → **ECS** → **ECS Task**
3. Role name: `MLPlatformECSTaskRole`
4. Create the role
5. Then attach the policy as described above
