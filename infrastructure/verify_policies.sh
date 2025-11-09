#!/bin/bash
# Script to verify which policies are attached to each role

set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Get account ID if not set
if [ -z "$AWS_ACCOUNT_ID" ]; then
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
fi

ADMIN_POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/MLPlatformAdminPolicy"

echo "========================================="
echo "Verifying IAM Role Policy Attachments"
echo "========================================="
echo ""

# Check Lambda Role
echo "1. MLPlatformLambdaRole:"
if aws iam get-role --role-name MLPlatformLambdaRole >/dev/null 2>&1; then
    echo "   Role exists ✓"
    echo "   Attached policies:"
    if aws iam list-attached-role-policies --role-name MLPlatformLambdaRole 2>/dev/null | grep -q "PolicyArn"; then
        aws iam list-attached-role-policies --role-name MLPlatformLambdaRole --query 'AttachedPolicies[*].PolicyArn' --output table 2>/dev/null || echo "   (Could not list policies - may need permissions)"
        
        # Check if admin policy is attached
        if aws iam list-attached-role-policies --role-name MLPlatformLambdaRole 2>/dev/null | grep -q "$ADMIN_POLICY_ARN"; then
            echo "   ✓ MLPlatformAdminPolicy is attached"
        else
            echo "   ⚠️  MLPlatformAdminPolicy is NOT attached"
        fi
    else
        echo "   (Could not list policies - may need permissions)"
    fi
else
    echo "   Role does NOT exist"
fi
echo ""

# Check ECS Task Role
echo "2. MLPlatformECSTaskRole:"
if aws iam get-role --role-name MLPlatformECSTaskRole >/dev/null 2>&1; then
    echo "   Role exists ✓"
    echo "   Attached policies:"
    if aws iam list-attached-role-policies --role-name MLPlatformECSTaskRole 2>/dev/null | grep -q "PolicyArn"; then
        aws iam list-attached-role-policies --role-name MLPlatformECSTaskRole --query 'AttachedPolicies[*].PolicyArn' --output table 2>/dev/null || echo "   (Could not list policies - may need permissions)"
        
        # Check if admin policy is attached
        if aws iam list-attached-role-policies --role-name MLPlatformECSTaskRole 2>/dev/null | grep -q "$ADMIN_POLICY_ARN"; then
            echo "   ✓ MLPlatformAdminPolicy is attached"
        else
            echo "   ⚠️  MLPlatformAdminPolicy is NOT attached"
        fi
    else
        echo "   (Could not list policies - may need permissions)"
    fi
else
    echo "   Role does NOT exist"
fi
echo ""

# Check ECS Execution Role
echo "3. MLPlatformECSTaskExecutionRole:"
if aws iam get-role --role-name MLPlatformECSTaskExecutionRole >/dev/null 2>&1; then
    echo "   Role exists ✓"
    echo "   Attached policies:"
    if aws iam list-attached-role-policies --role-name MLPlatformECSTaskExecutionRole 2>/dev/null | grep -q "PolicyArn"; then
        aws iam list-attached-role-policies --role-name MLPlatformECSTaskExecutionRole --query 'AttachedPolicies[*].PolicyArn' --output table 2>/dev/null || echo "   (Could not list policies - may need permissions)"
        echo "   Note: This role uses AWS managed policy (AmazonECSTaskExecutionRolePolicy)"
        echo "   This is correct - ECS execution roles need the AWS managed policy"
    else
        echo "   (Could not list policies - may need permissions)"
    fi
else
    echo "   Role does NOT exist"
fi
echo ""

# Check if MLPlatformAdminPolicy exists
echo "4. MLPlatformAdminPolicy:"
if aws iam get-policy --policy-arn "$ADMIN_POLICY_ARN" >/dev/null 2>&1; then
    echo "   ✓ Policy exists: $ADMIN_POLICY_ARN"
else
    echo "   ⚠️  Policy does NOT exist"
    echo "   Create it first using: infrastructure/MLPlatformAdminPolicy.json"
fi
echo ""

echo "========================================="
echo "Summary"
echo "========================================="
echo ""
echo "Expected setup:"
echo "  - MLPlatformLambdaRole → MLPlatformAdminPolicy"
echo "  - MLPlatformECSTaskRole → MLPlatformAdminPolicy"
echo "  - MLPlatformECSTaskExecutionRole → AmazonECSTaskExecutionRolePolicy (AWS managed)"
echo ""
echo "To attach MLPlatformAdminPolicy to roles, run:"
echo "  ./infrastructure/setup_iam_roles_simple.sh"
echo ""

