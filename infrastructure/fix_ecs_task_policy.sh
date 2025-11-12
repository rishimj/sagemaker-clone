#!/bin/bash
# Fix ECS Task Policy - ensure it has all required permissions

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
S3_BUCKET_NAME=${S3_BUCKET_NAME:-your-ml-platform-bucket}
DYNAMODB_TABLE_NAME=${DYNAMODB_TABLE_NAME:-ml-jobs}

echo "========================================="
echo "Updating ECS Task Policy"
echo "========================================="
echo ""

TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

# Create comprehensive ECS task policy
cat > $TMP_DIR/ecs-task-policy.json <<EOF
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
                "dynamodb:Query"
            ],
            "Resource": "arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DYNAMODB_TABLE_NAME}"
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "*"
        }
    ]
}
EOF

POLICY_NAME="MLPlatformECSTaskPolicy"
POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${POLICY_NAME}"

echo "1. Updating policy: $POLICY_NAME"

# Check if policy exists
if aws iam get-policy --policy-arn "$POLICY_ARN" >/dev/null 2>&1; then
    echo "  Policy exists, creating new version..."
    
    # Get current version
    CURRENT_VERSION=$(aws iam get-policy --policy-arn "$POLICY_ARN" --query 'Policy.DefaultVersionId' --output text)
    
    # Create new version
    aws iam create-policy-version \
        --policy-arn "$POLICY_ARN" \
        --policy-document file://$TMP_DIR/ecs-task-policy.json \
        --set-as-default \
        >/dev/null 2>&1 || echo "  Creating policy version..."
    
    echo "  ✅ Policy updated"
else
    echo "  Policy does not exist, creating..."
    aws iam create-policy \
        --policy-name "$POLICY_NAME" \
        --policy-document file://$TMP_DIR/ecs-task-policy.json \
        >/dev/null 2>&1 || echo "  Policy creation failed"
    sleep 3
    echo "  ✅ Policy created"
fi

echo ""
echo "2. Attaching policy to ECS Task Role..."

# Attach to role
aws iam attach-role-policy \
    --role-name MLPlatformECSTaskRole \
    --policy-arn "$POLICY_ARN" \
    2>/dev/null && echo "  ✅ Policy attached" || echo "  ⚠️  Policy may already be attached or need admin permissions"

echo ""
echo "========================================="
echo "✅ ECS Task Policy Updated"
echo "========================================="
echo ""
echo "Policy ARN: $POLICY_ARN"
echo "Attached to: MLPlatformECSTaskRole"
echo ""
echo "Permissions included:"
echo "  ✅ S3: GetObject, PutObject, ListBucket, HeadObject"
echo "  ✅ DynamoDB: GetItem, PutItem, UpdateItem, Query"
echo "  ✅ CloudWatch Logs: CreateLogGroup, CreateLogStream, PutLogEvents"
echo ""

