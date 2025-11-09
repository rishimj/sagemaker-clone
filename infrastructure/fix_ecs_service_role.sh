#!/bin/bash
set -e

echo "========================================="
echo "Fixing ECS Service Linked Role"
echo "========================================="
echo ""

# The ECS service linked role should be created automatically,
# but sometimes it needs to be created manually

echo "1. Creating ECS service linked role..."

# Check if role already exists
if aws iam get-role --role-name AWSServiceRoleForECS 2>/dev/null; then
    echo "  ✓ ECS service linked role already exists"
else
    echo "  Creating ECS service linked role..."
    aws iam create-service-linked-role \
        --aws-service-name ecs.amazonaws.com \
        2>&1 || echo "  Note: Role may already exist or creation may have failed"
fi

echo ""
echo "2. Verifying role exists..."
if aws iam get-role --role-name AWSServiceRoleForECS >/dev/null 2>&1; then
    echo "  ✓ ECS service linked role verified"
else
    echo "  ⚠️  ECS service linked role not found"
    echo ""
    echo "  You may need to create it manually via AWS Console:"
    echo "  1. Go to IAM → Roles"
    echo "  2. Click 'Create role'"
    echo "  3. Select 'AWS service' → 'ECS' → 'ECS'"
    echo "  4. Click 'Next' → 'Create role'"
    echo ""
    echo "  Or run this command (requires admin permissions):"
    echo "  aws iam create-service-linked-role --aws-service-name ecs.amazonaws.com"
fi

echo ""
echo "========================================="
echo "✓ ECS Service Role Check Complete"
echo "========================================="

