#!/bin/bash
# Verify and fix ECS IAM permissions

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
S3_BUCKET_NAME=${S3_BUCKET_NAME:-ml-platform-618574523116-71448}
DYNAMODB_TABLE_NAME=${DYNAMODB_TABLE_NAME:-ml-jobs}

echo "========================================="
echo "Verifying ECS IAM Permissions"
echo "========================================="
echo ""

# Check ECS Task Execution Role
echo "1. Checking ECS Task Execution Role..."
EXEC_ROLE="MLPlatformECSTaskExecutionRole"

if aws iam get-role --role-name "$EXEC_ROLE" >/dev/null 2>&1; then
    echo "  ✅ Role exists: $EXEC_ROLE"
    
    # Check if AmazonECSTaskExecutionRolePolicy is attached
    if aws iam list-attached-role-policies --role-name "$EXEC_ROLE" 2>/dev/null | grep -q "AmazonECSTaskExecutionRolePolicy"; then
        echo "  ✅ AmazonECSTaskExecutionRolePolicy attached"
    else
        echo "  ⚠️  AmazonECSTaskExecutionRolePolicy NOT attached - attaching now..."
        aws iam attach-role-policy \
            --role-name "$EXEC_ROLE" \
            --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy \
            2>/dev/null || echo "  Failed to attach (may need admin permissions)"
    fi
else
    echo "  ❌ Role does not exist: $EXEC_ROLE"
    echo "  Run: ./infrastructure/setup_iam_roles.sh"
    exit 1
fi

echo ""

# Check ECS Task Role
echo "2. Checking ECS Task Role..."
TASK_ROLE="MLPlatformECSTaskRole"

if aws iam get-role --role-name "$TASK_ROLE" >/dev/null 2>&1; then
    echo "  ✅ Role exists: $TASK_ROLE"
    
    # Check if MLPlatformECSTaskPolicy is attached
    TASK_POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/MLPlatformECSTaskPolicy"
    if aws iam list-attached-role-policies --role-name "$TASK_ROLE" 2>/dev/null | grep -q "MLPlatformECSTaskPolicy"; then
        echo "  ✅ MLPlatformECSTaskPolicy attached"
    else
        echo "  ⚠️  MLPlatformECSTaskPolicy NOT attached - creating and attaching..."
        
        # Create policy
        TMP_DIR=$(mktemp -d)
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
        
        # Delete existing policy if it exists
        aws iam delete-policy --policy-arn "$TASK_POLICY_ARN" 2>/dev/null || true
        sleep 2
        
        # Create policy
        aws iam create-policy \
            --policy-name MLPlatformECSTaskPolicy \
            --policy-document file://$TMP_DIR/ecs-task-policy.json \
            >/dev/null 2>&1 || echo "  Policy may already exist"
        
        # Attach to role
        aws iam attach-role-policy \
            --role-name "$TASK_ROLE" \
            --policy-arn "$TASK_POLICY_ARN" \
            2>/dev/null || echo "  Failed to attach (may need admin permissions)"
        
        rm -rf $TMP_DIR
    fi
else
    echo "  ❌ Role does not exist: $TASK_ROLE"
    echo "  Run: ./infrastructure/setup_iam_roles.sh"
    exit 1
fi

echo ""

# Verify task definition uses correct roles
echo "3. Checking ECS Task Definition..."
TASK_DEF="training-job"

if aws ecs describe-task-definition --task-definition "$TASK_DEF" --region "$AWS_REGION" >/dev/null 2>&1; then
    echo "  ✅ Task definition exists: $TASK_DEF"
    
    TD_OUTPUT=$(aws ecs describe-task-definition --task-definition "$TASK_DEF" --region "$AWS_REGION" --query 'taskDefinition.{executionRoleArn:executionRoleArn,taskRoleArn:taskRoleArn}' --output json)
    EXEC_ROLE_ARN=$(echo "$TD_OUTPUT" | python3 -c "import sys, json; print(json.load(sys.stdin)['executionRoleArn'])" 2>/dev/null || echo "")
    TASK_ROLE_ARN=$(echo "$TD_OUTPUT" | python3 -c "import sys, json; print(json.load(sys.stdin)['taskRoleArn'])" 2>/dev/null || echo "")
    
    EXPECTED_EXEC_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${EXEC_ROLE}"
    EXPECTED_TASK_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${TASK_ROLE}"
    
    if [ "$EXEC_ROLE_ARN" == "$EXPECTED_EXEC_ARN" ]; then
        echo "  ✅ Execution role ARN correct: $EXEC_ROLE_ARN"
    else
        echo "  ⚠️  Execution role ARN mismatch:"
        echo "     Expected: $EXPECTED_EXEC_ARN"
        echo "     Found:    $EXEC_ROLE_ARN"
    fi
    
    if [ "$TASK_ROLE_ARN" == "$EXPECTED_TASK_ARN" ]; then
        echo "  ✅ Task role ARN correct: $TASK_ROLE_ARN"
    else
        echo "  ⚠️  Task role ARN mismatch:"
        echo "     Expected: $EXPECTED_TASK_ARN"
        echo "     Found:    $TASK_ROLE_ARN"
    fi
else
    echo "  ⚠️  Task definition does not exist: $TASK_DEF"
    echo "  Run: ./infrastructure/create_task_definition.sh"
fi

echo ""
echo "========================================="
echo "✅ ECS IAM Permissions Verification Complete"
echo "========================================="
echo ""
echo "Summary:"
echo "  - ECS Task Execution Role: $EXEC_ROLE"
echo "    → AmazonECSTaskExecutionRolePolicy (for ECR pull & CloudWatch logs)"
echo "  - ECS Task Role: $TASK_ROLE"
echo "    → MLPlatformECSTaskPolicy (for S3, DynamoDB, CloudWatch logs)"
echo ""
echo "If permissions are missing, you may need admin access to attach policies."
echo ""

