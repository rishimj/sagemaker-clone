# Infrastructure Setup Scripts

This directory contains scripts to set up AWS infrastructure for the ML Platform.

## Prerequisites

1. AWS CLI installed and configured
2. Docker installed (for building and pushing images)
3. `.env` file in the project root with the following variables:
   ```
   AWS_REGION=us-east-1
   AWS_ACCOUNT_ID=123456789012
   S3_BUCKET_NAME=ml-platform-bucket
   DYNAMODB_TABLE_NAME=ml-jobs
   ECS_CLUSTER_NAME=training-cluster
   SUBNET_ID=subnet-xxxxx
   ```

## Scripts

### `setup_all.sh`

Main setup script that creates all AWS resources:

- S3 bucket (with versioning enabled)
- DynamoDB table
- ECR repository
- ECS cluster

**Usage:**

```bash
./infrastructure/setup_all.sh
```

### Individual Setup Scripts

#### `setup_s3.sh`

Creates S3 bucket for storing datasets and models.

**Usage:**

```bash
./infrastructure/setup_s3.sh
```

#### `setup_dynamodb.sh`

Creates DynamoDB table for job metadata.

**Usage:**

```bash
./infrastructure/setup_dynamodb.sh
```

#### `setup_ecr.sh`

Creates ECR repository for Docker images.

**Usage:**

```bash
./infrastructure/setup_ecr.sh
```

#### `setup_ecs.sh`

Creates ECS cluster for running training tasks.

**Usage:**

```bash
./infrastructure/setup_ecs.sh
```

### `build_and_push_docker.sh`

Builds the training Docker image and pushes it to ECR.

**Usage:**

```bash
./infrastructure/build_and_push_docker.sh
```

**Note:** This script:

1. Builds the Docker image from `training/Dockerfile`
2. Tags it for ECR
3. Logs into ECR
4. Pushes the image

## Setup Order

1. Run `setup_all.sh` to create all infrastructure
2. Run `build_and_push_docker.sh` to build and push the training image
3. Create ECS task definition (manual step)
4. Deploy Lambda functions (manual step)
5. Set up API Gateway (manual step)

## Troubleshooting

### Script fails with "Error: .env file not found"

- Make sure you have a `.env` file in the project root
- Copy `env.example` to `.env` and fill in your values

### Script fails with "Bucket already exists"

- This is normal if the bucket was already created
- The script will continue with the next steps

### Docker build fails

- Make sure Docker is running
- Check that `training/Dockerfile` exists
- Verify all dependencies in `training/requirements.txt` are valid

### ECR push fails

- Make sure you're logged into AWS CLI
- Verify your AWS credentials have ECR permissions
- Check that the ECR repository was created successfully

## Next Steps After Infrastructure Setup

1. **Create ECS Task Definition:**

   ```bash
   aws ecs register-task-definition \
     --cli-input-json file://task-definition.json
   ```

2. **Deploy Lambda Functions:**

   - Package Lambda functions with dependencies
   - Create Lambda deployment packages
   - Deploy to AWS Lambda

3. **Set up API Gateway:**

   - Create REST API
   - Create resources and methods
   - Connect to Lambda functions
   - Deploy API

4. **Configure IAM Roles:**
   - Create IAM role for ECS tasks
   - Create IAM role for Lambda functions
   - Attach appropriate policies

## AWS Resources Created

- **S3 Bucket:** `s3://${S3_BUCKET_NAME}`

  - Used for storing datasets and trained models
  - Versioning enabled

- **DynamoDB Table:** `${DYNAMODB_TABLE_NAME}`

  - Primary key: `job_id` (String)
  - Billing mode: Pay per request

- **ECR Repository:** `training`

  - Used for storing Docker training images
  - URI: `${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/training`

- **ECS Cluster:** `${ECS_CLUSTER_NAME}`
  - Used for running training tasks
  - Fargate launch type

## Cleanup

To remove all infrastructure:

```bash
# Delete ECS cluster
aws ecs delete-cluster --cluster ${ECS_CLUSTER_NAME} --region ${AWS_REGION}

# Delete ECR repository (must delete images first)
aws ecr delete-repository --repository-name training --force --region ${AWS_REGION}

# Delete DynamoDB table
aws dynamodb delete-table --table-name ${DYNAMODB_TABLE_NAME} --region ${AWS_REGION}

# Delete S3 bucket (must empty first)
aws s3 rm s3://${S3_BUCKET_NAME} --recursive
aws s3 rb s3://${S3_BUCKET_NAME} --region ${AWS_REGION}
```

**Warning:** This will delete all data in these resources!
