#!/bin/bash
set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

echo "Creating DynamoDB table: ${DYNAMODB_TABLE_NAME}"

# Create table
aws dynamodb create-table \
    --table-name ${DYNAMODB_TABLE_NAME} \
    --attribute-definitions AttributeName=job_id,AttributeType=S \
    --key-schema AttributeName=job_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region ${AWS_REGION} 2>/dev/null || echo "Table already exists"

# Wait for table to be active
aws dynamodb wait table-exists --table-name ${DYNAMODB_TABLE_NAME} --region ${AWS_REGION}

echo "✓ DynamoDB table ready: ${DYNAMODB_TABLE_NAME}"

