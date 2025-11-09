#!/bin/bash
set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Warning: .env file not found, using defaults"
fi

AWS_REGION=${AWS_REGION:-us-east-1}
POLICY_NAME="MLPlatformAdminPolicy"
USER_NAME="ml-platform-admin"

echo "========================================="
echo "Fixing Network Permissions (EC2 Access)"
echo "========================================="
echo ""

# Get account ID if not set
if [ -z "$AWS_ACCOUNT_ID" ]; then
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")
    if [ -z "$AWS_ACCOUNT_ID" ]; then
        echo "❌ Error: Could not get AWS account ID"
        echo "   Please set AWS_ACCOUNT_ID in your .env file or ensure AWS credentials are configured"
        exit 1
    fi
fi

POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${POLICY_NAME}"

echo "Account ID: $AWS_ACCOUNT_ID"
echo "Policy ARN: $POLICY_ARN"
echo "User: $USER_NAME"
echo ""

# Check if policy file exists
if [ ! -f "infrastructure/MLPlatformAdminPolicy.json" ]; then
    echo "❌ Error: Policy file not found: infrastructure/MLPlatformAdminPolicy.json"
    exit 1
fi

# Step 1: Check if policy exists
echo "Step 1: Checking if policy exists..."
if aws iam get-policy --policy-arn "$POLICY_ARN" >/dev/null 2>&1; then
    echo "   ✅ Policy exists"
    POLICY_EXISTS=true
else
    echo "   ⚠️  Policy does not exist, will create it"
    POLICY_EXISTS=false
fi

# Step 2: Create or update policy
echo ""
echo "Step 2: Creating/updating policy with EC2 permissions..."

if [ "$POLICY_EXISTS" = true ]; then
    # Policy exists - create new version
    echo "   Creating new policy version..."
    aws iam create-policy-version \
        --policy-arn "$POLICY_ARN" \
        --policy-document file://infrastructure/MLPlatformAdminPolicy.json \
        --set-as-default >/dev/null 2>&1 && {
        echo "   ✅ Policy updated successfully"
    } || {
        echo "   ⚠️  Could not update policy (may need to delete old versions first)"
        echo "   Attempting to delete old versions..."
        
        # List all policy versions
        VERSIONS=$(aws iam list-policy-versions --policy-arn "$POLICY_ARN" --query 'Versions[?IsDefaultVersion==`false`].VersionId' --output text 2>/dev/null || echo "")
        
        if [ -n "$VERSIONS" ]; then
            for VERSION in $VERSIONS; do
                echo "   Deleting old version: $VERSION"
                aws iam delete-policy-version --policy-arn "$POLICY_ARN" --version-id "$VERSION" 2>/dev/null || true
            done
        fi
        
        # Try again
        aws iam create-policy-version \
            --policy-arn "$POLICY_ARN" \
            --policy-document file://infrastructure/MLPlatformAdminPolicy.json \
            --set-as-default >/dev/null 2>&1 && {
            echo "   ✅ Policy updated successfully"
        } || {
            echo "   ❌ Failed to update policy"
            echo "   You may need admin permissions to update the policy"
            echo ""
            echo "   Please ask an AWS admin to run:"
            echo "     aws iam create-policy-version \\"
            echo "         --policy-arn $POLICY_ARN \\"
            echo "         --policy-document file://infrastructure/MLPlatformAdminPolicy.json \\"
            echo "         --set-as-default"
            exit 1
        }
    }
else
    # Policy doesn't exist - create it
    echo "   Creating new policy..."
    aws iam create-policy \
        --policy-name "$POLICY_NAME" \
        --policy-document file://infrastructure/MLPlatformAdminPolicy.json >/dev/null 2>&1 && {
        echo "   ✅ Policy created successfully"
    } || {
        echo "   ❌ Failed to create policy"
        echo "   You may need admin permissions to create the policy"
        echo ""
        echo "   Please ask an AWS admin to run:"
        echo "     aws iam create-policy \\"
        echo "         --policy-name $POLICY_NAME \\"
        echo "         --policy-document file://infrastructure/MLPlatformAdminPolicy.json"
        exit 1
    }
fi

# Step 3: Attach policy to user
echo ""
echo "Step 3: Attaching policy to user: $USER_NAME..."

# Check if policy is already attached
ATTACHED=$(aws iam list-attached-user-policies --user-name "$USER_NAME" --query "AttachedPolicies[?PolicyArn=='$POLICY_ARN'].PolicyArn" --output text 2>/dev/null || echo "")

if [ "$ATTACHED" = "$POLICY_ARN" ]; then
    echo "   ✅ Policy is already attached to user"
else
    echo "   Attaching policy..."
    aws iam attach-user-policy \
        --user-name "$USER_NAME" \
        --policy-arn "$POLICY_ARN" 2>&1 && {
        echo "   ✅ Policy attached successfully"
    } || {
        echo "   ⚠️  Could not attach policy automatically"
        echo "   Error details above"
        echo ""
        echo "   You may need admin permissions to attach the policy."
        echo "   Please ask an AWS admin to run:"
        echo "     aws iam attach-user-policy \\"
        echo "         --user-name $USER_NAME \\"
        echo "         --policy-arn $POLICY_ARN"
        echo ""
        echo "   Or use the AWS Console:"
        echo "     1. Go to: https://console.aws.amazon.com/iam/home#/users/$USER_NAME"
        echo "     2. Click 'Add permissions' → 'Attach policies directly'"
        echo "     3. Search for: $POLICY_NAME"
        echo "     4. Check the box and click 'Add permissions'"
        exit 1
    }
fi

echo ""
echo "========================================="
echo "✅ Network Permissions Fix Complete"
echo "========================================="
echo ""
echo "The policy now includes these EC2 permissions:"
echo "  ✅ ec2:DescribeVpcs"
echo "  ✅ ec2:DescribeSubnets"
echo "  ✅ ec2:DescribeSecurityGroups"
echo "  ✅ ec2:DescribeNetworkInterfaces"
echo "  ✅ ec2:DescribeAvailabilityZones"
echo "  ✅ ec2:DescribeRegions"
echo "  ✅ ec2:DescribeRouteTables"
echo "  ✅ ec2:DescribeInternetGateways"
echo "  ✅ ec2:DescribeNatGateways"
echo ""
echo "Note: It may take 10-15 seconds for permissions to propagate."
echo "Wait a moment, then run your test again:"
echo "  python tests/test_ecs_container_startup.py"
echo ""

