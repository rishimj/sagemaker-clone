#!/bin/bash
set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

echo "Creating S3 bucket: ${S3_BUCKET_NAME}"

# Check if bucket exists
if aws s3api head-bucket --bucket ${S3_BUCKET_NAME} --region ${AWS_REGION} 2>/dev/null; then
    echo "✓ Bucket already exists: ${S3_BUCKET_NAME}"
else
    echo "Creating bucket..."
    
    # Try to create bucket
    if aws s3 mb s3://${S3_BUCKET_NAME} --region ${AWS_REGION} 2>&1; then
        echo "✓ Bucket created successfully"
    else
        echo "✗ Error: Could not create bucket"
        echo ""
        echo "Possible reasons:"
        echo "  1. Bucket name is already taken (S3 bucket names are globally unique)"
        echo "  2. Insufficient permissions"
        echo "  3. Invalid bucket name"
        echo ""
        echo "Solution: Choose a different bucket name in .env file:"
        echo "  S3_BUCKET_NAME=ml-platform-bucket-YOURUNIQUENAME"
        exit 1
    fi
fi

# Enable versioning
echo "Enabling versioning..."
aws s3api put-bucket-versioning \
    --bucket ${S3_BUCKET_NAME} \
    --versioning-configuration Status=Enabled \
    --region ${AWS_REGION} 2>/dev/null || echo "  Versioning may already be enabled"

echo "✓ S3 bucket ready: s3://${S3_BUCKET_NAME}"

