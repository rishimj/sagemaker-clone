#!/bin/bash
set -e

# Script to fix Lambda IAM policy (requires admin permissions)
# This script updates the MLPlatformLambdaPolicy with correct DynamoDB permissions

echo "========================================="
echo "Fixing Lambda IAM Policy"
echo "========================================="
echo ""

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

# Get account ID if not set
if [ -z "$AWS_ACCOUNT_ID" ]; then
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
fi

REGION=${AWS_REGION:-us-east-1}
S3_BUCKET_NAME=${S3_BUCKET_NAME:-ml-platform-618574523116-71448}
DYNAMODB_TABLE_NAME=${DYNAMODB_TABLE_NAME:-ml-jobs}

POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/MLPlatformLambdaPolicy"

# Create temp directory
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

echo "1. Creating policy document..."

# Create policy document
cat > $TMP_DIR/lambda-policy.json <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:ListBucket",
                "s3:HeadObject"
            ],
            "Resource": [
                "arn:aws:s3:::${S3_BUCKET_NAME}",
                "arn:aws:s3:::${S3_BUCKET_NAME}/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:Scan",
                "dynamodb:Query",
                "dynamodb:DescribeTable"
            ],
            "Resource": "arn:aws:dynamodb:${REGION}:${AWS_ACCOUNT_ID}:table/${DYNAMODB_TABLE_NAME}"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ecs:RunTask",
                "ecs:DescribeTasks",
                "ecs:DescribeTaskDefinition"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": "iam:PassRole",
            "Resource": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/MLPlatformECSTaskRole"
        }
    ]
}
EOF

echo "  ✓ Policy document created"

echo ""
echo "2. Checking if policy exists..."

# Check if policy exists
if aws iam get-policy --policy-arn "$POLICY_ARN" >/dev/null 2>&1; then
    echo "  Policy exists, creating new version..."
    
    # Create new policy version
    aws iam create-policy-version \
        --policy-arn "$POLICY_ARN" \
        --policy-document file://$TMP_DIR/lambda-policy.json \
        --set-as-default
    
    echo "  ✓ Policy version created"
else
    echo "  Policy doesn't exist, creating new policy..."
    
    # Create new policy
    aws iam create-policy \
        --policy-name MLPlatformLambdaPolicy \
        --policy-document file://$TMP_DIR/lambda-policy.json
    
    sleep 2
    echo "  ✓ Policy created"
fi

echo ""
echo "3. Attaching policy to role..."

# Attach policy to role
aws iam attach-role-policy \
    --role-name MLPlatformLambdaRole \
    --policy-arn "$POLICY_ARN" 2>/dev/null || echo "  Policy already attached"

echo "  ✓ Policy attached to role"

echo ""
echo "========================================="
echo "✓ Lambda IAM policy updated!"
echo "========================================="
echo ""
echo "Policy ARN: $POLICY_ARN"
echo ""
echo "Note: IAM changes can take 10-15 seconds to propagate."
echo "Wait a moment, then test the API."
echo ""

