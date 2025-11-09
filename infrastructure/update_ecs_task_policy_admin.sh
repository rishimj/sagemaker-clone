#!/bin/bash
# This script updates the ECS Task Policy with all required DynamoDB permissions
# Requires IAM admin permissions to run

set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Get account ID if not set
if [ -z "$AWS_ACCOUNT_ID" ]; then
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    echo "Detected AWS Account ID: $AWS_ACCOUNT_ID"
fi

echo "========================================="
echo "Updating ECS Task Policy"
echo "========================================="
echo ""

POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/MLPlatformECSTaskPolicy"

# Create updated policy document with all DynamoDB permissions
cat > /tmp/ecs-task-policy.json <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:ListBucket"
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

echo "Policy document created with all DynamoDB permissions:"
echo "  - dynamodb:GetItem"
echo "  - dynamodb:PutItem"
echo "  - dynamodb:UpdateItem"
echo "  - dynamodb:Scan (NEW)"
echo "  - dynamodb:Query (NEW)"
echo "  - dynamodb:DescribeTable (NEW)"
echo ""

# Check if policy exists
if aws iam get-policy --policy-arn "$POLICY_ARN" >/dev/null 2>&1; then
    echo "Policy exists. Creating new version..."
    
    # Get current default version
    CURRENT_VERSION=$(aws iam get-policy --policy-arn "$POLICY_ARN" --query 'Policy.DefaultVersionId' --output text)
    echo "  Current version: $CURRENT_VERSION"
    
    # Create new policy version
    NEW_VERSION=$(aws iam create-policy-version \
        --policy-arn "$POLICY_ARN" \
        --policy-document file:///tmp/ecs-task-policy.json \
        --set-as-default \
        --query 'PolicyVersion.VersionId' --output text)
    
    echo "  New version created: $NEW_VERSION"
    echo "  New version set as default"
    
    # List all versions
    echo ""
    echo "Policy versions:"
    aws iam list-policy-versions --policy-arn "$POLICY_ARN" --query 'Versions[*].[VersionId,IsDefaultVersion,CreateDate]' --output table
    
    # Optional: Delete old versions if there are more than 5 (IAM limit)
    VERSION_COUNT=$(aws iam list-policy-versions --policy-arn "$POLICY_ARN" --query 'length(Versions)' --output text)
    if [ "$VERSION_COUNT" -gt 5 ]; then
        echo ""
        echo "Warning: Policy has more than 5 versions. Consider deleting old versions."
        echo "To delete old version:"
        echo "  aws iam delete-policy-version --policy-arn $POLICY_ARN --version-id $CURRENT_VERSION"
    fi
    
else
    echo "Policy does not exist. Creating new policy..."
    aws iam create-policy \
        --policy-name MLPlatformECSTaskPolicy \
        --policy-document file:///tmp/ecs-task-policy.json
    
    echo "  ✓ Policy created"
    
    # Attach to role
    echo "Attaching policy to ECS Task Role..."
    aws iam attach-role-policy \
        --role-name MLPlatformECSTaskRole \
        --policy-arn "$POLICY_ARN"
    
    echo "  ✓ Policy attached to role"
fi

echo ""
echo "========================================="
echo "✓ ECS Task Policy updated successfully!"
echo "========================================="
echo ""
echo "Verify the update:"
echo "  pytest tests/test_ecs_task_dynamodb_permissions.py -v"
echo ""

# Cleanup
rm -f /tmp/ecs-task-policy.json

