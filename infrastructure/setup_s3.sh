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

# Create bucket
aws s3 mb s3://${S3_BUCKET_NAME} --region ${AWS_REGION} 2>/dev/null || echo "Bucket already exists"

# Enable versioning
aws s3api put-bucket-versioning \
    --bucket ${S3_BUCKET_NAME} \
    --versioning-configuration Status=Enabled \
    --region ${AWS_REGION}

echo "✓ S3 bucket ready: s3://${S3_BUCKET_NAME}"

