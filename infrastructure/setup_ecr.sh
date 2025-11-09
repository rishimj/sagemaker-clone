#!/bin/bash
set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

echo "Creating ECR repository: training"

# Create repository
aws ecr create-repository \
    --repository-name training \
    --region ${AWS_REGION} 2>/dev/null || echo "Repository already exists"

echo "✓ ECR repository ready: training"
echo "  Repository URI: ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/training"

