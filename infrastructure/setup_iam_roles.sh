#!/bin/bash
set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

echo "========================================="
echo "Setting up IAM Roles for ML Platform"
echo "========================================="
echo ""

# Get account ID if not set
if [ -z "$AWS_ACCOUNT_ID" ]; then
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    echo "Detected AWS Account ID: $AWS_ACCOUNT_ID"
fi

# Create temp directory for policy files
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

echo "1. Creating Lambda Execution Role..."

# Lambda trust policy
cat > $TMP_DIR/lambda-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create Lambda role (ignore if exists)
aws iam create-role \
  --role-name MLPlatformLambdaRole \
  --assume-role-policy-document file://$TMP_DIR/lambda-trust-policy.json \
  2>/dev/null || echo "  Lambda role already exists"

# Attach basic execution policy
aws iam attach-role-policy \
  --role-name MLPlatformLambdaRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
  2>/dev/null || echo "  Policy already attached"

echo "  ✓ Lambda execution role ready"

echo ""
echo "2. Creating Lambda custom policy..."

# Lambda custom policy
cat > $TMP_DIR/lambda-policy.json <<EOF
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

# Update policy using policy version (keeps same ARN)
LAMBDA_POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/MLPlatformLambdaPolicy"

# Check if policy exists
if aws iam get-policy --policy-arn "$LAMBDA_POLICY_ARN" >/dev/null 2>&1; then
    # Policy exists - create new version
    echo "  Updating existing policy..."
    aws iam create-policy-version \
        --policy-arn "$LAMBDA_POLICY_ARN" \
        --policy-document file://$TMP_DIR/lambda-policy.json \
        --set-as-default \
        > /dev/null 2>&1 || echo "  Creating policy version..."
else
    # Policy doesn't exist - create it
    echo "  Creating new policy..."
    aws iam create-policy \
        --policy-name MLPlatformLambdaPolicy \
        --policy-document file://$TMP_DIR/lambda-policy.json \
        > /dev/null 2>&1
    sleep 3
fi

# Ensure policy is attached to role
aws iam attach-role-policy \
    --role-name MLPlatformLambdaRole \
    --policy-arn "$LAMBDA_POLICY_ARN" \
    2>/dev/null || echo "  Policy already attached"

echo "  Policy ARN: $LAMBDA_POLICY_ARN"

echo "  ✓ Lambda custom policy ready"

echo ""
echo "3. Creating ECS Task Execution Role..."

# ECS trust policy
cat > $TMP_DIR/ecs-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create ECS task execution role
aws iam create-role \
  --role-name MLPlatformECSTaskExecutionRole \
  --assume-role-policy-document file://$TMP_DIR/ecs-trust-policy.json \
  2>/dev/null || echo "  ECS task execution role already exists"

# Attach execution policy
aws iam attach-role-policy \
  --role-name MLPlatformECSTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy \
  2>/dev/null || echo "  Policy already attached"

echo "  ✓ ECS task execution role ready"

echo ""
echo "4. Creating ECS Task Role..."

# Create ECS task role
aws iam create-role \
  --role-name MLPlatformECSTaskRole \
  --assume-role-policy-document file://$TMP_DIR/ecs-trust-policy.json \
  2>/dev/null || echo "  ECS task role already exists"

echo "  ✓ ECS task role created"

echo ""
echo "5. Creating ECS Task Policy..."

# ECS task policy
cat > $TMP_DIR/ecs-task-policy.json <<EOF
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

# Create policy
aws iam delete-policy --policy-arn "arn:aws:iam::${AWS_ACCOUNT_ID}:policy/MLPlatformECSTaskPolicy" 2>/dev/null || true
sleep 2

aws iam create-policy \
  --policy-name MLPlatformECSTaskPolicy \
  --policy-document file://$TMP_DIR/ecs-task-policy.json \
  2>/dev/null || echo "  Policy already exists (will try to attach)"

# Attach to ECS task role
aws iam attach-role-policy \
  --role-name MLPlatformECSTaskRole \
  --policy-arn "arn:aws:iam::${AWS_ACCOUNT_ID}:policy/MLPlatformECSTaskPolicy" \
  2>/dev/null || echo "  Policy already attached"

echo "  ✓ ECS task policy ready"

echo ""
echo "========================================="
echo "✓ IAM Roles setup complete!"
echo "========================================="
echo ""
echo "Created Roles:"
echo "  - MLPlatformLambdaRole"
echo "  - MLPlatformECSTaskExecutionRole"
echo "  - MLPlatformECSTaskRole"
echo ""
echo "Role ARNs:"
echo "  Lambda: arn:aws:iam::${AWS_ACCOUNT_ID}:role/MLPlatformLambdaRole"
echo "  ECS Execution: arn:aws:iam::${AWS_ACCOUNT_ID}:role/MLPlatformECSTaskExecutionRole"
echo "  ECS Task: arn:aws:iam::${AWS_ACCOUNT_ID}:role/MLPlatformECSTaskRole"

