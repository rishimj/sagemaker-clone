#!/bin/bash
# Attempt to trigger AWS to auto-create the ECS service-linked role
# by creating an ECS service

set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

AWS_REGION=${AWS_REGION:-us-east-1}
ECS_CLUSTER=${ECS_CLUSTER_NAME:-training-cluster}
SUBNET_ID=${SUBNET_ID}
SERVICE_NAME="trigger-role-creation-$(date +%s)"

echo "========================================="
echo "Triggering ECS Service-Linked Role Creation"
echo "========================================="
echo ""

echo "1. Checking if role already exists..."
if aws iam get-role --role-name AWSServiceRoleForECS 2>/dev/null; then
    echo "  ✅ Role already exists!"
    exit 0
fi

echo "  Role doesn't exist, will try to trigger creation..."
echo ""

echo "2. Creating ECS service to trigger role creation..."
echo "  Service name: $SERVICE_NAME"
echo "  Cluster: $ECS_CLUSTER"
echo "  Task definition: training-job:1"

# Create service with desired count 0 (so it doesn't actually run tasks)
aws ecs create-service \
    --cluster "$ECS_CLUSTER" \
    --service-name "$SERVICE_NAME" \
    --task-definition training-job:1 \
    --desired-count 0 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_ID],assignPublicIp=ENABLED}" \
    --region "$AWS_REGION" \
    2>&1 | tee /tmp/ecs_service_create.log

SERVICE_CREATE_EXIT=$?

echo ""
echo "3. Waiting 5 seconds for role creation..."
sleep 5

echo ""
echo "4. Checking if role was created..."
if aws iam get-role --role-name AWSServiceRoleForECS 2>/dev/null; then
    echo "  ✅ Role was auto-created!"
    ROLE_CREATED=true
else
    echo "  ❌ Role still doesn't exist"
    ROLE_CREATED=false
fi

echo ""
echo "5. Cleaning up test service..."
aws ecs delete-service \
    --cluster "$ECS_CLUSTER" \
    --service "$SERVICE_NAME" \
    --region "$AWS_REGION" \
    2>/dev/null || echo "  Service may not have been created or already deleted"

echo ""
echo "========================================="
if [ "$ROLE_CREATED" = true ]; then
    echo "✅ Success! ECS service-linked role was created"
    echo ""
    echo "You can now test ECS tasks:"
    echo "  python tests/test_ecs_task_manual.py"
    exit 0
else
    echo "⚠️  Role was not auto-created"
    echo ""
    echo "Possible reasons:"
    echo "  1. Account restrictions on service-linked roles"
    echo "  2. Need to enable service-linked roles"
    echo "  3. Need to contact AWS Support"
    echo ""
    echo "Check the service creation log:"
    echo "  cat /tmp/ecs_service_create.log"
    exit 1
fi

