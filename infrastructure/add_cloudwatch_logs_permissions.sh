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
POLICY_NAME="MLPlatformCloudWatchLogsPolicy"
USER_NAME="ml-platform-admin"

echo "========================================="
echo "Adding CloudWatch Logs Permissions"
echo "========================================="
echo ""

# Get account ID if not set
if [ -z "$AWS_ACCOUNT_ID" ]; then
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
fi

echo "1. Creating CloudWatch Logs policy..."

# Policy document
cat > /tmp/cloudwatch-logs-policy.json <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:DescribeLogGroups",
                "logs:DescribeLogStreams",
                "logs:GetLogEvents",
                "logs:FilterLogEvents",
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:${AWS_REGION}:${AWS_ACCOUNT_ID}:log-group:/ecs/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:DescribeLogGroups",
                "logs:DescribeLogStreams"
            ],
            "Resource": "*"
        }
    ]
}
EOF

POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${POLICY_NAME}"

# Check if policy exists
if aws iam get-policy --policy-arn "$POLICY_ARN" >/dev/null 2>&1; then
    echo "   Policy exists, creating new version..."
    aws iam create-policy-version \
        --policy-arn "$POLICY_ARN" \
        --policy-document file:///tmp/cloudwatch-logs-policy.json \
        --set-as-default > /dev/null 2>&1 || echo "   ⚠️  Could not update policy (may need admin permissions)"
else
    echo "   Creating new policy..."
    aws iam create-policy \
        --policy-name "$POLICY_NAME" \
        --policy-document file:///tmp/cloudwatch-logs-policy.json > /dev/null 2>&1 || echo "   ⚠️  Could not create policy (may need admin permissions)"
fi

echo "   ✅ Policy created/updated: $POLICY_ARN"

echo ""
echo "2. Attaching policy to user: $USER_NAME..."
aws iam attach-user-policy \
    --user-name "$USER_NAME" \
    --policy-arn "$POLICY_ARN" 2>&1 && echo "   ✅ Policy attached" || echo "   ⚠️  Could not attach policy (may need admin permissions or policy may already be attached)"

echo ""
echo "========================================="
echo "✅ CloudWatch Logs Permissions Added"
echo "========================================="
echo ""
echo "Note: It may take a few seconds for permissions to propagate."
echo "Wait 10-15 seconds, then run: ./infrastructure/get_ecs_logs.sh"
echo ""

rm -f /tmp/cloudwatch-logs-policy.json

