#!/bin/bash
set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

echo "========================================="
echo "AWS ML Platform - Infrastructure Setup"
echo "========================================="
echo ""
echo "Region: $AWS_REGION"
echo "Account: $AWS_ACCOUNT_ID"
echo ""

# S3 Bucket
echo "1. Creating S3 bucket..."
# Check if bucket exists
if aws s3api head-bucket --bucket ${S3_BUCKET_NAME} --region ${AWS_REGION} 2>/dev/null; then
    echo "  Bucket already exists"
else
    # Create bucket
    aws s3 mb s3://${S3_BUCKET_NAME} --region ${AWS_REGION}
    echo "  Bucket created"
fi

# Enable versioning (only if bucket exists)
if aws s3api head-bucket --bucket ${S3_BUCKET_NAME} --region ${AWS_REGION} 2>/dev/null; then
    aws s3api put-bucket-versioning \
        --bucket ${S3_BUCKET_NAME} \
        --versioning-configuration Status=Enabled \
        --region ${AWS_REGION} 2>/dev/null || echo "  Note: Versioning may already be enabled"
    echo "  ✓ S3 bucket ready"
else
    echo "  ✗ Error: Bucket does not exist and could not be created"
    exit 1
fi

# DynamoDB Table
echo "2. Creating DynamoDB table..."
aws dynamodb create-table \
    --table-name ${DYNAMODB_TABLE_NAME} \
    --attribute-definitions AttributeName=job_id,AttributeType=S \
    --key-schema AttributeName=job_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region ${AWS_REGION} 2>/dev/null || echo "  Table already exists"

aws dynamodb wait table-exists --table-name ${DYNAMODB_TABLE_NAME} --region ${AWS_REGION}
echo "  ✓ DynamoDB table ready"

# ECR Repository
echo "3. Creating ECR repository..."
aws ecr create-repository \
    --repository-name training \
    --region ${AWS_REGION} 2>/dev/null || echo "  Repository already exists"

echo "  ✓ ECR repository ready"

# ECS Cluster
echo "4. Creating ECS cluster..."
aws ecs create-cluster \
    --cluster-name ${ECS_CLUSTER_NAME} \
    --region ${AWS_REGION} 2>/dev/null || echo "  Cluster already exists"

echo "  ✓ ECS cluster ready"

echo ""
echo "========================================="
echo "✓ Infrastructure setup complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Build and push your training Docker image to ECR"
echo "2. Create ECS task definition"
echo "3. Deploy Lambda functions"
echo "4. Set up API Gateway"

