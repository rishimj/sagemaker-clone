#!/bin/bash
set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

echo "Creating ECS cluster: ${ECS_CLUSTER_NAME}"

# Create cluster
aws ecs create-cluster \
    --cluster-name ${ECS_CLUSTER_NAME} \
    --region ${AWS_REGION} 2>/dev/null || echo "Cluster already exists"

echo "✓ ECS cluster ready: ${ECS_CLUSTER_NAME}"

