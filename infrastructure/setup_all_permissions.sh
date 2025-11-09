#!/bin/bash
set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Warning: .env file not found, using defaults"
    AWS_REGION=${AWS_REGION:-us-east-1}
fi

echo "========================================="
echo "Setting up ALL IAM Permissions via CLI"
echo "========================================="
echo ""

# Get account ID and current user
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
CURRENT_USER_ARN=$(aws sts get-caller-identity --query 'Arn' --output text)
CURRENT_USER=$(echo $CURRENT_USER_ARN | cut -d'/' -f2)

echo "AWS Account ID: $AWS_ACCOUNT_ID"
echo "Current IAM User: $CURRENT_USER"
echo "Region: $AWS_REGION"
echo ""

# Create temp directory for policy files
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

# ============================================================================
# Step 1: Add EC2 Permissions to Current User
# ============================================================================
echo "1. Adding EC2 permissions to current user: $CURRENT_USER"

# Create EC2 read policy
cat > $TMP_DIR/ec2-read-policy.json <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeVpcs",
                "ec2:DescribeSubnets",
                "ec2:DescribeSecurityGroups",
                "ec2:DescribeAvailabilityZones",
                "ec2:DescribeInstances",
                "ec2:DescribeNetworkInterfaces"
            ],
            "Resource": "*"
        }
    ]
}
EOF

POLICY_NAME="EC2ReadOnlyForMLPlatform"
POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${POLICY_NAME}"

# Delete existing policy if it exists
aws iam delete-policy --policy-arn "$POLICY_ARN" 2>/dev/null || true
sleep 2

# Create policy (only if we have permission)
if aws iam create-policy \
    --policy-name "$POLICY_NAME" \
    --policy-document file://$TMP_DIR/ec2-read-policy.json \
    2>/dev/null; then
    echo "  ✓ Policy created"
elif aws iam get-policy --policy-arn "$POLICY_ARN" &>/dev/null; then
    echo "  ✓ Policy already exists"
else
    echo "  ⚠ Could not create policy (may not have permission)"
fi

# Try to attach managed policy to user
set +e  # Temporarily disable exit on error for this section
ATTACH_OUTPUT=$(aws iam attach-user-policy \
    --user-name "$CURRENT_USER" \
    --policy-arn "$POLICY_ARN" \
    2>&1)
ATTACH_EXIT_CODE=$?

if [ $ATTACH_EXIT_CODE -eq 0 ]; then
    echo "  ✓ Managed policy attached to user"
else
    # Check if policy is already attached
    if aws iam list-attached-user-policies --user-name "$CURRENT_USER" 2>/dev/null | grep -q "$POLICY_ARN" 2>/dev/null; then
        echo "  ✓ Policy already attached to user"
    elif echo "$ATTACH_OUTPUT" | grep -q "AccessDenied"; then
        # Fallback: Try inline policy if managed policy attachment fails due to AccessDenied
        echo "  ⚠ Cannot attach managed policy (AccessDenied), trying inline policy..."
        if aws iam put-user-policy \
            --user-name "$CURRENT_USER" \
            --policy-name "${POLICY_NAME}Inline" \
            --policy-document file://$TMP_DIR/ec2-read-policy.json \
            2>/dev/null; then
            echo "  ✓ Inline policy added to user"
        else
            echo "  ⚠ Warning: Could not attach policy to user (AccessDenied)"
            echo "  ⚠ You may need an AWS admin to attach the policy manually:"
            echo "     aws iam attach-user-policy --user-name $CURRENT_USER --policy-arn $POLICY_ARN"
            echo "  ⚠ Or attach via AWS Console: IAM → Users → $CURRENT_USER → Add permissions"
            echo "  ⚠ Continuing with setup (other permissions may still work)..."
        fi
    else
        echo "  ⚠ Could not attach policy: $ATTACH_OUTPUT"
        echo "  ⚠ Continuing with setup..."
    fi
fi
set -e  # Re-enable exit on error
echo ""

# ============================================================================
# Step 2: Create Lambda Execution Role
# ============================================================================
echo "2. Creating Lambda Execution Role..."

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

# Create Lambda role
aws iam create-role \
  --role-name MLPlatformLambdaRole \
  --assume-role-policy-document file://$TMP_DIR/lambda-trust-policy.json \
  2>/dev/null || echo "  Lambda role already exists"

# Attach basic execution policy
aws iam attach-role-policy \
  --role-name MLPlatformLambdaRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
  2>/dev/null || echo "  Basic execution policy already attached"

echo "  ✓ Lambda execution role ready"
echo ""

# ============================================================================
# Step 3: Create Lambda Custom Policy
# ============================================================================
echo "3. Creating Lambda custom policy..."

# Get S3 bucket and DynamoDB table names from .env or use defaults
S3_BUCKET_NAME=${S3_BUCKET_NAME:-ml-platform-bucket}
DYNAMODB_TABLE_NAME=${DYNAMODB_TABLE_NAME:-ml-jobs}
ECS_CLUSTER_NAME=${ECS_CLUSTER_NAME:-training-cluster}

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
            "Resource": "arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DYNAMODB_TABLE_NAME}"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ecs:RunTask",
                "ecs:DescribeTasks",
                "ecs:DescribeTaskDefinition",
                "ecs:ListTasks"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": "iam:PassRole",
            "Resource": [
                "arn:aws:iam::${AWS_ACCOUNT_ID}:role/MLPlatformECSTaskRole",
                "arn:aws:iam::${AWS_ACCOUNT_ID}:role/MLPlatformECSTaskExecutionRole"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
                "logs:DescribeLogGroups"
            ],
            "Resource": "*"
        }
    ]
}
EOF

LAMBDA_POLICY_NAME="MLPlatformLambdaPolicy"
LAMBDA_POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${LAMBDA_POLICY_NAME}"

# Delete existing policy if it exists
aws iam delete-policy --policy-arn "$LAMBDA_POLICY_ARN" 2>/dev/null || true
sleep 2

# Create policy
aws iam create-policy \
  --policy-name "$LAMBDA_POLICY_NAME" \
  --policy-document file://$TMP_DIR/lambda-policy.json \
  2>/dev/null || echo "  Policy already exists, continuing..."

# Attach to Lambda role
aws iam attach-role-policy \
  --role-name MLPlatformLambdaRole \
  --policy-arn "$LAMBDA_POLICY_ARN" \
  2>/dev/null || echo "  Policy already attached to role"

echo "  ✓ Lambda custom policy ready"
echo ""

# ============================================================================
# Step 4: Create ECS Task Execution Role
# ============================================================================
echo "4. Creating ECS Task Execution Role..."

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
  2>/dev/null || echo "  Execution policy already attached"

echo "  ✓ ECS task execution role ready"
echo ""

# ============================================================================
# Step 5: Create ECS Task Role
# ============================================================================
echo "5. Creating ECS Task Role..."

# Create ECS task role
aws iam create-role \
  --role-name MLPlatformECSTaskRole \
  --assume-role-policy-document file://$TMP_DIR/ecs-trust-policy.json \
  2>/dev/null || echo "  ECS task role already exists"

echo "  ✓ ECS task role created"
echo ""

# ============================================================================
# Step 6: Create ECS Task Policy
# ============================================================================
echo "6. Creating ECS Task Policy..."

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

ECS_POLICY_NAME="MLPlatformECSTaskPolicy"
ECS_POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${ECS_POLICY_NAME}"

# Delete existing policy if it exists
aws iam delete-policy --policy-arn "$ECS_POLICY_ARN" 2>/dev/null || true
sleep 2

# Create policy
aws iam create-policy \
  --policy-name "$ECS_POLICY_NAME" \
  --policy-document file://$TMP_DIR/ecs-task-policy.json \
  2>/dev/null || echo "  Policy already exists, continuing..."

# Attach to ECS task role
aws iam attach-role-policy \
  --role-name MLPlatformECSTaskRole \
  --policy-arn "$ECS_POLICY_ARN" \
  2>/dev/null || echo "  Policy already attached to role"

echo "  ✓ ECS task policy ready"
echo ""

# ============================================================================
# Step 7: Add Full ML Platform Permissions to Current User (Optional but Recommended)
# ============================================================================
echo "7. Adding ML Platform permissions to current user..."

# Create comprehensive policy for user
cat > $TMP_DIR/user-ml-platform-policy.json <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:*",
                "dynamodb:*",
                "ecr:*",
                "ecs:*",
                "lambda:*",
                "apigateway:*",
                "logs:*",
                "iam:CreateRole",
                "iam:DeleteRole",
                "iam:AttachRolePolicy",
                "iam:DetachRolePolicy",
                "iam:PutRolePolicy",
                "iam:DeleteRolePolicy",
                "iam:GetRole",
                "iam:ListRolePolicies",
                "iam:ListAttachedRolePolicies",
                "iam:PassRole",
                "iam:CreatePolicy",
                "iam:DeletePolicy",
                "iam:GetPolicy",
                "iam:AttachUserPolicy",
                "iam:DetachUserPolicy",
                "ec2:DescribeVpcs",
                "ec2:DescribeSubnets",
                "ec2:DescribeSecurityGroups",
                "ec2:DescribeAvailabilityZones"
            ],
            "Resource": "*"
        }
    ]
}
EOF

USER_POLICY_NAME="MLPlatformFullAccess"
USER_POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${USER_POLICY_NAME}"

# Delete existing policy if it exists (only if we have permission)
aws iam delete-policy --policy-arn "$USER_POLICY_ARN" 2>/dev/null || true
sleep 2

# Create policy (only if we have permission)
if aws iam create-policy \
    --policy-name "$USER_POLICY_NAME" \
    --policy-document file://$TMP_DIR/user-ml-platform-policy.json \
    2>/dev/null; then
    echo "  ✓ User policy created"
elif aws iam get-policy --policy-arn "$USER_POLICY_ARN" &>/dev/null; then
    echo "  ✓ User policy already exists"
else
    echo "  ⚠ Could not create user policy (may not have permission)"
fi

# Try to attach managed policy to user
set +e  # Temporarily disable exit on error for this section
ATTACH_OUTPUT=$(aws iam attach-user-policy \
    --user-name "$CURRENT_USER" \
    --policy-arn "$USER_POLICY_ARN" \
    2>&1)
ATTACH_EXIT_CODE=$?

if [ $ATTACH_EXIT_CODE -eq 0 ]; then
    echo "  ✓ Managed policy attached to user"
else
    # Check if policy is already attached
    if aws iam list-attached-user-policies --user-name "$CURRENT_USER" 2>/dev/null | grep -q "$USER_POLICY_ARN" 2>/dev/null; then
        echo "  ✓ User policy already attached"
    elif echo "$ATTACH_OUTPUT" | grep -q "AccessDenied"; then
        # Fallback: Try inline policy if managed policy attachment fails due to AccessDenied
        echo "  ⚠ Cannot attach managed policy (AccessDenied), trying inline policy..."
        if aws iam put-user-policy \
            --user-name "$CURRENT_USER" \
            --policy-name "${USER_POLICY_NAME}Inline" \
            --policy-document file://$TMP_DIR/user-ml-platform-policy.json \
            2>/dev/null; then
            echo "  ✓ Inline policy added to user"
        else
            echo "  ⚠ Warning: Could not attach user policy (AccessDenied)"
            echo "  ⚠ You may need an AWS admin to attach the policy manually:"
            echo "     aws iam attach-user-policy --user-name $CURRENT_USER --policy-arn $USER_POLICY_ARN"
            echo "  ⚠ Or attach via AWS Console: IAM → Users → $CURRENT_USER → Add permissions"
            echo "  ⚠ Continuing with setup (other permissions may still work)..."
        fi
    else
        echo "  ⚠ Could not attach policy: $ATTACH_OUTPUT"
        echo "  ⚠ Continuing with setup..."
    fi
fi
set -e  # Re-enable exit on error

echo "  ✓ ML Platform permissions setup attempted (see warnings above if any)"
echo ""

# ============================================================================
# Summary
# ============================================================================
echo "========================================="
echo "✓ All IAM Permissions Setup Complete!"
echo "========================================="
echo ""
echo "Created/Updated:"
echo "  ✓ EC2 read permissions for user: $CURRENT_USER"
echo "  ✓ Lambda execution role: MLPlatformLambdaRole"
echo "  ✓ Lambda custom policy: MLPlatformLambdaPolicy"
echo "  ✓ ECS task execution role: MLPlatformECSTaskExecutionRole"
echo "  ✓ ECS task role: MLPlatformECSTaskRole"
echo "  ✓ ECS task policy: MLPlatformECSTaskPolicy"
echo "  ✓ Full ML Platform permissions for user: $CURRENT_USER"
echo ""
echo "Role ARNs:"
echo "  Lambda: arn:aws:iam::${AWS_ACCOUNT_ID}:role/MLPlatformLambdaRole"
echo "  ECS Execution: arn:aws:iam::${AWS_ACCOUNT_ID}:role/MLPlatformECSTaskExecutionRole"
echo "  ECS Task: arn:aws:iam::${AWS_ACCOUNT_ID}:role/MLPlatformECSTaskRole"
echo ""
echo "⚠️  Note: It may take 10-15 seconds for permissions to propagate."
echo "   Wait a moment before running other scripts."
echo ""
echo "Next steps:"
echo "  1. Wait 10-15 seconds for permissions to propagate"
echo "  2. Run: ./infrastructure/get_vpc_info.sh"
echo "  3. Update .env file with subnet ID"
echo "  4. Continue with infrastructure setup"

