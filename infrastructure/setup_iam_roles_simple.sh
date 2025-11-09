#!/bin/bash
# Simplified IAM setup - uses MLPlatformAdminPolicy for all services
# This is simpler for development/testing, but less secure for production

set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

echo "========================================="
echo "Simplified IAM Roles Setup"
echo "Using MLPlatformAdminPolicy for all services"
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

ADMIN_POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/MLPlatformAdminPolicy"

# Create admin policy if it doesn't exist
echo "Checking for MLPlatformAdminPolicy..."
if ! aws iam get-policy --policy-arn "$ADMIN_POLICY_ARN" >/dev/null 2>&1; then
    echo "  MLPlatformAdminPolicy does not exist. Creating it..."
    
    # Create comprehensive admin policy
    cat > $TMP_DIR/admin-policy.json <<EOF
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
    
    # Try to create the policy
    if aws iam create-policy \
        --policy-name MLPlatformAdminPolicy \
        --policy-document file://$TMP_DIR/admin-policy.json \
        --description "Comprehensive policy for ML Platform services - S3, DynamoDB, ECS, Lambda, etc." \
        2>&1; then
        echo "  ✓ MLPlatformAdminPolicy created successfully"
    else
        echo "  ⚠️  Could not create MLPlatformAdminPolicy (may need admin permissions)"
        echo "  Please create it manually via AWS Console or ask an admin to create it"
        echo ""
        echo "  Policy document saved to: $TMP_DIR/admin-policy.json"
        echo "  You can copy this to AWS Console → IAM → Policies → Create Policy → JSON"
        exit 1
    fi
else
    echo "  ✓ Found existing MLPlatformAdminPolicy: $ADMIN_POLICY_ARN"
fi

echo ""

# ============================================================================
# Step 1: Create Lambda Execution Role
# ============================================================================
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
  2>/dev/null || echo "  Basic execution policy already attached"

# Attach admin policy
echo "  Attaching MLPlatformAdminPolicy to Lambda role..."
aws iam attach-role-policy \
  --role-name MLPlatformLambdaRole \
  --policy-arn "$ADMIN_POLICY_ARN" \
  2>/dev/null || echo "  Admin policy already attached"

echo "  ✓ Lambda execution role ready"
echo ""

# ============================================================================
# Step 2: Create ECS Task Execution Role
# ============================================================================
echo "2. Creating ECS Task Execution Role..."

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

# Attach execution policy (required for ECS to pull images and write logs)
aws iam attach-role-policy \
  --role-name MLPlatformECSTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy \
  2>/dev/null || echo "  Execution policy already attached"

echo "  ✓ ECS task execution role ready"
echo ""

# ============================================================================
# Step 3: Create ECS Task Role
# ============================================================================
echo "3. Creating ECS Task Role..."

# Create ECS task role
aws iam create-role \
  --role-name MLPlatformECSTaskRole \
  --assume-role-policy-document file://$TMP_DIR/ecs-trust-policy.json \
  2>/dev/null || echo "  ECS task role already exists"

# Attach admin policy
echo "  Attaching MLPlatformAdminPolicy to ECS Task role..."
aws iam attach-role-policy \
  --role-name MLPlatformECSTaskRole \
  --policy-arn "$ADMIN_POLICY_ARN" \
  2>/dev/null || echo "  Admin policy already attached"

echo "  ✓ ECS task role ready"
echo ""

# ============================================================================
# Summary
# ============================================================================
echo "========================================="
echo "✓ Simplified IAM Roles setup complete!"
echo "========================================="
echo ""
echo "All services are now using MLPlatformAdminPolicy:"
echo "  - MLPlatformLambdaRole"
echo "  - MLPlatformECSTaskRole"
echo ""
echo "Note: ECS Task Execution Role uses AmazonECSTaskExecutionRolePolicy"
echo "      (required by AWS for ECS to pull images and write logs)"
echo ""
echo "This is simpler for development but less secure than separate policies."
echo "For production, consider using the full setup: ./infrastructure/setup_iam_roles.sh"
echo ""

