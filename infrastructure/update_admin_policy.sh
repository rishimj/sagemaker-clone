#!/bin/bash
set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

AWS_REGION=${AWS_REGION:-us-east-1}
POLICY_NAME="MLPlatformAdminPolicy"
USER_NAME="ml-platform-admin"

echo "========================================="
echo "Updating ML Platform Admin Policy"
echo "========================================="
echo ""

# Get account ID if not set
if [ -z "$AWS_ACCOUNT_ID" ]; then
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
fi

POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${POLICY_NAME}"

echo "1. Checking if policy exists: $POLICY_NAME"
if aws iam get-policy --policy-arn "$POLICY_ARN" >/dev/null 2>&1; then
    echo "   ✅ Policy exists"
    echo "   Creating new version..."
    
    # Create new policy version
    aws iam create-policy-version \
        --policy-arn "$POLICY_ARN" \
        --policy-document file://infrastructure/MLPlatformAdminPolicy_UPDATED.json \
        --set-as-default >/dev/null 2>&1 && {
        echo "   ✅ Policy updated successfully"
    } || {
        echo "   ❌ Failed to update policy"
        echo "   You may need admin permissions to update the policy"
        exit 1
    }
else
    echo "   ⚠️  Policy does not exist"
    echo "   Creating new policy..."
    
    # Create new policy
    aws iam create-policy \
        --policy-name "$POLICY_NAME" \
        --policy-document file://infrastructure/MLPlatformAdminPolicy_UPDATED.json >/dev/null 2>&1 && {
        echo "   ✅ Policy created successfully"
    } || {
        echo "   ❌ Failed to create policy"
        echo "   You may need admin permissions to create the policy"
        exit 1
    }
fi

echo ""
echo "2. Attaching policy to user: $USER_NAME..."
aws iam attach-user-policy \
    --user-name "$USER_NAME" \
    --policy-arn "$POLICY_ARN" 2>&1 && {
    echo "   ✅ Policy attached successfully"
} || {
    echo "   ⚠️  Could not attach policy (may already be attached or need admin permissions)"
}

echo ""
echo "========================================="
echo "✅ Policy Update Complete"
echo "========================================="
echo ""
echo "New permissions added:"
echo "  ✅ CloudWatch Logs: DescribeLogStreams, GetLogEvents, FilterLogEvents"
echo "  ✅ IAM: ListAttachedRolePolicies, ListUserPolicies, GetPolicy, etc."
echo "  ✅ IAM: CreatePolicy, DeletePolicy, CreatePolicyVersion, etc."
echo "  ✅ IAM: AttachUserPolicy, PutUserPolicy, DeleteUserPolicy"
echo "  ✅ EC2: DescribeVpcs, DescribeSubnets, DescribeSecurityGroups"
echo "  ✅ CloudWatch: GetMetricStatistics, ListMetrics, DescribeAlarms"
echo "  ✅ STS: GetCallerIdentity, AssumeRole"
echo ""
echo "Note: It may take 10-15 seconds for permissions to propagate."
echo ""

