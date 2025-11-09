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
USER_NAME="ml-platform-admin"
POLICY_NAME="CloudWatchLogsAccess"

echo "========================================="
echo "Adding CloudWatch Logs Inline Policy"
echo "========================================="
echo ""

# Get account ID if not set
if [ -z "$AWS_ACCOUNT_ID" ]; then
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
fi

echo "1. Creating inline policy for user: $USER_NAME"

# Policy document
cat > /tmp/cloudwatch-logs-inline-policy.json <<EOF
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

echo "2. Putting inline policy..."
aws iam put-user-policy \
    --user-name "$USER_NAME" \
    --policy-name "$POLICY_NAME" \
    --policy-document file:///tmp/cloudwatch-logs-inline-policy.json 2>&1 && {
    echo "   ✅ Inline policy created successfully"
} || {
    echo "   ❌ Failed to create inline policy"
    echo "   Error details above"
    echo ""
    echo "   💡 Alternative: Ask an AWS admin to attach the policy"
    echo "   Policy ARN: arn:aws:iam::${AWS_ACCOUNT_ID}:policy/MLPlatformCloudWatchLogsPolicy"
    exit 1
}

echo ""
echo "========================================="
echo "✅ CloudWatch Logs Permissions Added"
echo "========================================="
echo ""
echo "Policy name: $POLICY_NAME"
echo "User: $USER_NAME"
echo ""
echo "Note: It may take a few seconds for permissions to propagate."
echo "Wait 10-15 seconds, then run: ./infrastructure/get_ecs_logs.sh"
echo ""

rm -f /tmp/cloudwatch-logs-inline-policy.json

