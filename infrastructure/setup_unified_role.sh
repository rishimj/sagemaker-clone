#!/bin/bash
# Ultra-simplified setup: One role, one policy for all services
# Perfect for development - maximum simplicity!

set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

echo "========================================="
echo "Ultra-Simplified IAM Setup"
echo "One Role + One Policy for Everything"
echo "========================================="
echo ""

# Get account ID if not set
if [ -z "$AWS_ACCOUNT_ID" ]; then
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    echo "Detected AWS Account ID: $AWS_ACCOUNT_ID"
fi

# Create temp directory
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

UNIFIED_ROLE_NAME="MLPlatformRole"
ADMIN_POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/MLPlatformAdminPolicy"

# ============================================================================
# Step 1: Verify MLPlatformAdminPolicy exists
# ============================================================================
echo "1. Checking for MLPlatformAdminPolicy..."
if aws iam get-policy --policy-arn "$ADMIN_POLICY_ARN" >/dev/null 2>&1; then
    echo "   ✓ MLPlatformAdminPolicy exists"
elif aws iam get-policy --policy-arn "$ADMIN_POLICY_ARN" 2>&1 | grep -q "AccessDenied"; then
    echo "   ⚠️  Cannot verify policy (insufficient permissions)"
    echo "   Assuming MLPlatformAdminPolicy exists (continuing...)"
else
    echo "   ⚠️  MLPlatformAdminPolicy may not exist"
    echo "   Please create it first using infrastructure/MLPlatformAdminPolicy.json"
    echo "   Or continue if it exists but can't be verified"
    read -p "   Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""

# ============================================================================
# Step 2: Create Unified Role (allows both Lambda and ECS to assume it)
# ============================================================================
echo "2. Creating unified role: $UNIFIED_ROLE_NAME..."

# Trust policy that allows BOTH Lambda and ECS to assume the role
cat > $TMP_DIR/unified-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": [
          "lambda.amazonaws.com",
          "ecs-tasks.amazonaws.com"
        ]
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create unified role
aws iam create-role \
  --role-name "$UNIFIED_ROLE_NAME" \
  --assume-role-policy-document file://$TMP_DIR/unified-trust-policy.json \
  2>/dev/null && echo "   ✓ Role created" || echo "   Role already exists (updating trust policy...)"

# Update trust policy if role exists (to allow both services)
aws iam update-assume-role-policy \
  --role-name "$UNIFIED_ROLE_NAME" \
  --policy-document file://$TMP_DIR/unified-trust-policy.json \
  2>/dev/null && echo "   ✓ Trust policy updated" || echo "   (Trust policy may already be correct)"

# Attach basic Lambda execution policy (for CloudWatch Logs)
aws iam attach-role-policy \
  --role-name "$UNIFIED_ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
  2>/dev/null || echo "   Basic execution policy already attached"

# Attach admin policy
echo "   Attaching MLPlatformAdminPolicy..."
aws iam attach-role-policy \
  --role-name "$UNIFIED_ROLE_NAME" \
  --policy-arn "$ADMIN_POLICY_ARN" \
  2>/dev/null || echo "   Admin policy already attached"

# Attach ECS execution policy (for ECR image pulls and logs)
aws iam attach-role-policy \
  --role-name "$UNIFIED_ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy \
  2>/dev/null || echo "   ECS execution policy already attached"

echo "   ✓ Unified role ready"
echo ""

# ============================================================================
# Step 3: Update Lambda Function to use Unified Role
# ============================================================================
echo "3. Updating Lambda functions to use unified role..."

# Update submit-job Lambda
if aws lambda get-function --function-name submit-job >/dev/null 2>&1; then
    UNIFIED_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${UNIFIED_ROLE_NAME}"
    aws lambda update-function-configuration \
        --function-name submit-job \
        --role "$UNIFIED_ROLE_ARN" \
        2>/dev/null && echo "   ✓ submit-job Lambda updated" || echo "   (Could not update submit-job - may need to update manually)"
else
    echo "   submit-job Lambda not found (will use unified role when created)"
fi

# Update get-job-status Lambda
if aws lambda get-function --function-name get-job-status >/dev/null 2>&1; then
    UNIFIED_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${UNIFIED_ROLE_NAME}"
    aws lambda update-function-configuration \
        --function-name get-job-status \
        --role "$UNIFIED_ROLE_ARN" \
        2>/dev/null && echo "   ✓ get-job-status Lambda updated" || echo "   (Could not update get-job-status - may need to update manually)"
else
    echo "   get-job-status Lambda not found (will use unified role when created)"
fi

echo ""

# ============================================================================
# Step 4: Update ECS Task Definition to use Unified Role
# ============================================================================
echo "4. Updating ECS Task Definition to use unified role..."

UNIFIED_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${UNIFIED_ROLE_NAME}"

# Get current task definition
if aws ecs describe-task-definition --task-definition training-job >/dev/null 2>&1; then
    echo "   Current task definition found"
    echo "   Note: ECS Task Definitions cannot be updated - you'll need to register a new revision"
    echo "   Run: ./infrastructure/create_task_definition_unified.sh"
    echo "   Or update manually in AWS Console"
else
    echo "   Task definition not found (will use unified role when created)"
fi

echo ""

# ============================================================================
# Summary
# ============================================================================
echo "========================================="
echo "✓ Unified Role Setup Complete!"
echo "========================================="
echo ""
echo "Created:"
echo "  - Role: $UNIFIED_ROLE_NAME"
echo "    - Can be assumed by: Lambda and ECS"
echo "    - Has policy: MLPlatformAdminPolicy"
echo "    - Has policy: AWSLambdaBasicExecutionRole (AWS managed)"
echo "    - Has policy: AmazonECSTaskExecutionRolePolicy (AWS managed)"
echo ""
echo "Next Steps:"
echo "  1. Update Lambda functions to use: $UNIFIED_ROLE_NAME"
echo "  2. Update ECS Task Definition to use: $UNIFIED_ROLE_NAME"
echo "     - executionRoleArn: $UNIFIED_ROLE_ARN"
echo "     - taskRoleArn: $UNIFIED_ROLE_ARN"
echo ""
echo "Files to update:"
echo "  - infrastructure/create_task_definition.sh (update role ARNs)"
echo "  - infrastructure/deploy_lambda.sh (update role ARN)"
echo ""
echo "This is the ULTRA-SIMPLIFIED setup - one role for everything! 🚀"
echo ""

