#!/bin/bash
set -e

if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

echo "Building training Docker image for linux/amd64 (required for ECS Fargate)..."

# Build from root directory so we can copy storage directory
# Use --platform linux/amd64 to ensure compatibility with ECS Fargate
docker build --platform linux/amd64 -t training:latest -f training/Dockerfile .

# Tag for ECR
docker tag training:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/training:latest

# Login to ECR
aws ecr get-login-password --region ${AWS_REGION} | \
    docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Push
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/training:latest

echo "✓ Docker image pushed to ECR"

