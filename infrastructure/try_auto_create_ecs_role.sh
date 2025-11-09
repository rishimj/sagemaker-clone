#!/bin/bash
# Sometimes AWS auto-creates the service linked role when you perform certain operations
# This script tries to trigger that auto-creation

set -e

echo "========================================="
echo "Attempting to Trigger ECS Role Auto-Creation"
echo "========================================="
echo ""

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

AWS_REGION=${AWS_REGION:-us-east-1}
ECS_CLUSTER=${ECS_CLUSTER_NAME:-training-cluster}

echo "1. Checking ECS cluster..."
aws ecs describe-clusters --clusters $ECS_CLUSTER --region $AWS_REGION > /dev/null
echo "  ✓ Cluster exists"

echo ""
echo "2. Listing task definitions..."
aws ecs list-task-definitions --region $AWS_REGION --max-items 1 > /dev/null
echo "  ✓ Can list task definitions"

echo ""
echo "3. Describing task definition..."
aws ecs describe-task-definition --task-definition training-job --region $AWS_REGION > /dev/null
echo "  ✓ Can describe task definition"

echo ""
echo "4. Checking if service linked role exists now..."
if aws iam get-role --role-name AWSServiceRoleForECS 2>/dev/null; then
    echo "  ✅ ECS service linked role exists!"
    exit 0
else
    echo "  ❌ ECS service linked role still doesn't exist"
    echo ""
    echo "  The role was not auto-created. You need to create it manually:"
    echo "  - See: infrastructure/create_ecs_service_role_console.md"
    echo "  - Or use AWS Console: IAM → Roles → Create role → AWS service → ECS"
    exit 1
fi

