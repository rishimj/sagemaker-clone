#!/bin/bash
set -e

# This script should be run by an AWS admin to attach EC2 permissions
# to the ml-platform-admin user

echo "========================================="
echo "Attaching EC2 Permissions (Admin Script)"
echo "========================================="
echo ""

USER_NAME="ml-platform-admin"

echo "This script will attach EC2 read-only permissions to user: $USER_NAME"
echo ""

# Option 1: Attach AWS managed policy (Easiest)
echo "Option 1: Attaching AWS managed policy (AmazonEC2ReadOnlyAccess)..."
aws iam attach-user-policy \
    --user-name "$USER_NAME" \
    --policy-arn arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess \
    2>/dev/null && echo "  ✓ Policy attached successfully" || echo "  Policy may already be attached or user doesn't exist"

echo ""
echo "✓ Done! User should now have EC2 read permissions."
echo ""
echo "Wait 10-15 seconds for permissions to propagate, then run:"
echo "  ./infrastructure/get_vpc_info.sh"

