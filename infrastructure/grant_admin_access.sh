#!/bin/bash
set -e

echo "========================================="
echo "Granting AWS Admin Access (Test Project)"
echo "========================================="
echo ""

# Get current user and account
CURRENT_USER_ARN=$(aws sts get-caller-identity --query 'Arn' --output text)
CURRENT_USER=$(echo $CURRENT_USER_ARN | cut -d'/' -f2)
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "AWS Account ID: $AWS_ACCOUNT_ID"
echo "Current IAM User: $CURRENT_USER"
echo ""

# Check if user already has admin access
echo "Checking current permissions..."
EXISTING_POLICIES=$(aws iam list-attached-user-policies --user-name "$CURRENT_USER" --query 'AttachedPolicies[].PolicyArn' --output text 2>/dev/null || echo "")

if echo "$EXISTING_POLICIES" | grep -q "AdministratorAccess"; then
    echo "✓ User already has AdministratorAccess policy attached!"
    echo ""
    echo "You're all set! You have admin privileges."
    exit 0
fi

echo ""
echo "Attempting to attach AdministratorAccess policy..."
echo ""

# Try to attach AdministratorAccess policy
if aws iam attach-user-policy \
    --user-name "$CURRENT_USER" \
    --policy-arn arn:aws:iam::aws:policy/AdministratorAccess \
    2>&1; then
    echo ""
    echo "========================================="
    echo "✓ SUCCESS! Admin access granted!"
    echo "========================================="
    echo ""
    echo "User: $CURRENT_USER"
    echo "Policy: AdministratorAccess"
    echo ""
    echo "⚠️  IMPORTANT: Wait 10-15 seconds for permissions to propagate"
    echo "   before running other AWS CLI commands."
    echo ""
    echo "Test your access:"
    echo "  aws iam list-attached-user-policies --user-name $CURRENT_USER"
    echo ""
else
    echo ""
    echo "========================================="
    echo "✗ FAILED: Could not attach admin policy"
    echo "========================================="
    echo ""
    echo "This usually means:"
    echo "  1. You don't have permission to attach policies to yourself"
    echo "  2. You need an AWS administrator to do this for you"
    echo "  3. Or you need to use root account credentials"
    echo ""
    echo "Solutions:"
    echo ""
    echo "Option 1: If you have root account access:"
    echo "  - Log in with root account credentials"
    echo "  - Run this script again"
    echo ""
    echo "Option 2: Ask an AWS admin to run:"
    echo "  aws iam attach-user-policy \\"
    echo "      --user-name $CURRENT_USER \\"
    echo "      --policy-arn arn:aws:iam::aws:policy/AdministratorAccess"
    echo ""
    echo "Option 3: Use AWS Console:"
    echo "  1. Go to: https://console.aws.amazon.com/iam"
    echo "  2. Users → $CURRENT_USER → Add permissions"
    echo "  3. Attach policies directly → AdministratorAccess"
    echo "  4. Add permissions"
    echo ""
    echo "Option 4: Create a new IAM user with admin access:"
    echo "  See: infrastructure/create_admin_user.sh"
    echo ""
    exit 1
fi

