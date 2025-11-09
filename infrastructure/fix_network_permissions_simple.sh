#!/bin/bash
set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

USER_NAME="ml-platform-admin"
MANAGED_POLICY_ARN="arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess"

echo "========================================="
echo "Fixing Network Permissions (Quick Fix)"
echo "========================================="
echo ""
echo "This script will attempt to attach the AWS managed policy"
echo "AmazonEC2ReadOnlyAccess to user: $USER_NAME"
echo ""
echo "If you don't have permission to attach policies, you'll need"
echo "to use the AWS Console or ask an admin to run this script."
echo ""

# Try to attach the managed policy
echo "Attempting to attach policy: $MANAGED_POLICY_ARN"
echo ""

aws iam attach-user-policy \
    --user-name "$USER_NAME" \
    --policy-arn "$MANAGED_POLICY_ARN" 2>&1 && {
    echo ""
    echo "========================================="
    echo "✅ SUCCESS: Policy attached!"
    echo "========================================="
    echo ""
    echo "The AmazonEC2ReadOnlyAccess policy has been attached to $USER_NAME"
    echo "This policy includes all EC2 read permissions needed for network checks:"
    echo "  ✅ ec2:DescribeVpcs"
    echo "  ✅ ec2:DescribeSubnets"
    echo "  ✅ ec2:DescribeSecurityGroups"
    echo "  ✅ ec2:DescribeNetworkInterfaces"
    echo "  ✅ ec2:DescribeAvailabilityZones"
    echo "  ✅ And many more EC2 read permissions"
    echo ""
    echo "Note: It may take 10-15 seconds for permissions to propagate."
    echo "Wait a moment, then run your test again:"
    echo "  python tests/test_ecs_container_startup.py"
    echo ""
} || {
    ERROR_CODE=$?
    echo ""
    echo "========================================="
    echo "❌ Failed to attach policy automatically"
    echo "========================================="
    echo ""
    echo "You don't have permission to attach policies to users."
    echo "Here are your options:"
    echo ""
    echo "OPTION 1: AWS Console (Easiest - 2 minutes)"
    echo "  1. Go to: https://console.aws.amazon.com/iam/home#/users/$USER_NAME"
    echo "  2. Click 'Add permissions' → 'Attach policies directly'"
    echo "  3. Search for: AmazonEC2ReadOnlyAccess"
    echo "  4. Check the box and click 'Next' → 'Add permissions'"
    echo "  5. Wait 10-15 seconds"
    echo "  6. Run your test again: python tests/test_ecs_container_startup.py"
    echo ""
    echo "OPTION 2: Ask AWS Admin to Run This Script"
    echo "  An AWS admin can run this same script:"
    echo "    ./infrastructure/fix_network_permissions_simple.sh"
    echo ""
    echo "OPTION 3: Admin Can Run AWS CLI Command"
    echo "  Ask an admin to run:"
    echo "    aws iam attach-user-policy \\"
    echo "        --user-name $USER_NAME \\"
    echo "        --policy-arn $MANAGED_POLICY_ARN"
    echo ""
    exit $ERROR_CODE
}

