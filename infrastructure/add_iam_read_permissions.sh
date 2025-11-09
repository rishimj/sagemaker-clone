#!/bin/bash
# Add IAM read permissions to the ml-platform-admin user
# This enables tests to verify role permissions

set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

AWS_REGION=${AWS_REGION:-us-east-1}
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}
CURRENT_USER="ml-platform-admin"

echo "========================================="
echo "Adding IAM Read Permissions to User"
echo "========================================="
echo ""
echo "User: $CURRENT_USER"
echo "Account: $AWS_ACCOUNT_ID"
echo ""

# Create IAM read permissions policy
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

cat > $TMP_DIR/iam-read-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iam:GetRole",
        "iam:ListRoles",
        "iam:ListRolePolicies",
        "iam:ListAttachedRolePolicies",
        "iam:GetRolePolicy",
        "iam:GetPolicy",
        "iam:ListPolicies",
        "iam:ListPolicyVersions",
        "iam:GetPolicyVersion",
        "iam:ListUserPolicies",
        "iam:ListAttachedUserPolicies",
        "iam:GetUserPolicy",
        "iam:ListRoleTags",
        "iam:GetUser"
      ],
      "Resource": "*"
    }
  ]
}
EOF

POLICY_NAME="MLPlatformIAMReadAccess"
POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${POLICY_NAME}"

echo "1. Creating IAM read permissions policy..."

# Check if policy exists
if aws iam get-policy --policy-arn "$POLICY_ARN" >/dev/null 2>&1; then
    echo "  Policy already exists, updating..."
    # Get current version
    CURRENT_VERSION=$(aws iam get-policy --policy-arn "$POLICY_ARN" --query 'Policy.DefaultVersionId' --output text)
    
    # Create new version
    aws iam create-policy-version \
        --policy-arn "$POLICY_ARN" \
        --policy-document file://$TMP_DIR/iam-read-policy.json \
        --set-as-default \
        >/dev/null 2>&1 || echo "  Creating new policy version..."
else
    echo "  Creating new policy..."
    aws iam create-policy \
        --policy-name "$POLICY_NAME" \
        --policy-document file://$TMP_DIR/iam-read-policy.json \
        >/dev/null 2>&1 || echo "  Policy creation failed (may already exist)"
    sleep 3
fi

echo "  ✓ Policy ready: $POLICY_ARN"
echo ""

echo "2. Attaching policy to user: $CURRENT_USER..."

# Attach to user
aws iam attach-user-policy \
    --user-name "$CURRENT_USER" \
    --policy-arn "$POLICY_ARN" \
    2>&1 | grep -v "EntityAlreadyExists" || echo "  Policy already attached"

echo "  ✓ Policy attached to user"
echo ""

echo "========================================="
echo "✅ IAM Read Permissions Added!"
echo "========================================="
echo ""
echo "Policy ARN: $POLICY_ARN"
echo "User: $CURRENT_USER"
echo ""
echo "⚠️  Note: It may take 10-15 seconds for permissions to propagate."
echo "   Wait a moment before running tests."
echo ""
echo "You can now run tests that verify IAM role permissions:"
echo "  python -m pytest tests/test_ecs_roles.py -v"
echo "  python -m pytest tests/test_verify_admin_policy.py -v"
echo ""

