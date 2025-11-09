# Create ECS Service Linked Role - AWS Console Steps

## Problem

Your IAM user doesn't have permissions to create service-linked roles via CLI. You need to create it via AWS Console.

## Quick Steps (2 minutes)

### Step 1: Open IAM Console

1. Go to **AWS Console** → **IAM** service
2. Click **"Roles"** in the left sidebar

### Step 2: Create Service Linked Role

1. Click **"Create role"** button
2. Select **"AWS service"** tab
3. Under **"Use cases for other AWS services"**, search for **"ECS"**
4. You should see **"Elastic Container Service"**
5. Select **"Elastic Container Service"** (the one that says "Allows ECS to manage resources on your behalf")
6. Click **"Next"** button
7. Review the role details:
   - Role name: `AWSServiceRoleForECS`
   - Description: "Allows Amazon ECS to create and manage AWS resources on your behalf."
8. Click **"Create role"**

### Step 3: Verify

1. Go back to **IAM → Roles**
2. Search for `AWSServiceRoleForECS`
3. You should see it in the list

## Alternative: Use Root Account

If you have access to the AWS root account, you can run:

```bash
aws iam create-service-linked-role --aws-service-name ecs.amazonaws.com
```

## After Creating the Role

Test that it works:

```bash
# Test ECS task
python tests/test_ecs_task_manual.py

# Or test full submission
python tests/test_submit_job_with_logging.py
```

## What This Role Does

The `AWSServiceRoleForECS` service-linked role allows Amazon ECS to:

- Create and manage ENIs (Elastic Network Interfaces) for Fargate tasks
- Pull container images from ECR
- Write logs to CloudWatch Logs
- Manage task networking in VPCs

**This is required for ECS Fargate tasks to run.**

## Troubleshooting

If the role creation fails:

1. Make sure you're using an account with admin permissions
2. Try using the root account
3. Check if the role already exists (it might be hidden)

If the role exists but tasks still fail:

1. Verify the role has the correct trust policy
2. Check ECS cluster permissions
3. Verify VPC/subnet configuration
