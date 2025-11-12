#!/bin/bash
# Verify that the ECS service-linked role exists and is configured correctly

echo "========================================="
echo "Verifying ECS Service-Linked Role"
echo "========================================="
echo ""

ROLE_NAME="AWSServiceRoleForECS"
EXPECTED_PATH="/aws-service-role/ecs.amazonaws.com/"

echo "1. Checking if role exists..."
if aws iam get-role --role-name "$ROLE_NAME" 2>/dev/null; then
    echo "  ✅ Role '$ROLE_NAME' exists"
    
    # Get role details
    ROLE_PATH=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Path' --output text 2>/dev/null)
    
    echo ""
    echo "2. Checking role path..."
    if [ "$ROLE_PATH" == "$EXPECTED_PATH" ]; then
        echo "  ✅ Role path is correct: $ROLE_PATH"
        echo ""
        echo "✅ ECS Service-Linked Role is correctly configured!"
        echo ""
        echo "You can now test ECS tasks:"
        echo "  python tests/test_ecs_task_manual.py"
        exit 0
    else
        echo "  ⚠️  Role path is: $ROLE_PATH"
        echo "  Expected: $EXPECTED_PATH"
        echo ""
        echo "  This might be a regular role, not a service-linked role."
    fi
else
    echo "  ❌ Role '$ROLE_NAME' does not exist"
    echo ""
    echo "  Please create the service-linked role via AWS Console:"
    echo "  See: docs/STEP_BY_STEP_ECS_ROLE.md"
    exit 1
fi

echo ""
echo "========================================="
echo "Role verification complete"
echo "========================================="

