#!/bin/bash
set -e

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

echo "========================================="
echo "Deploying Lambda Functions"
echo "========================================="
echo ""

# Create temp directory for packages
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

LAMBDA_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/MLPlatformLambdaRole"

echo "1. Packaging submit_job Lambda..."

# Create package directory
mkdir -p $TMP_DIR/submit_job

# Copy handler
cp lambda_functions/submit_job/handler.py $TMP_DIR/submit_job/

# Copy storage module
mkdir -p $TMP_DIR/submit_job/storage
cp storage/*.py $TMP_DIR/submit_job/storage/
cp storage/__init__.py $TMP_DIR/submit_job/storage/ 2>/dev/null || true

# Install dependencies
pip install -r lambda_functions/submit_job/requirements.txt -t $TMP_DIR/submit_job/ --quiet

# Create zip
cd $TMP_DIR/submit_job
zip -r ../submit_job.zip . -q
cd - > /dev/null

echo "  ✓ submit_job packaged"

echo ""
echo "2. Packaging get_job_status Lambda..."

# Create package directory
mkdir -p $TMP_DIR/get_job_status

# Copy handler
cp lambda_functions/get_job_status/handler.py $TMP_DIR/get_job_status/

# Copy storage module
mkdir -p $TMP_DIR/get_job_status/storage
cp storage/*.py $TMP_DIR/get_job_status/storage/
cp storage/__init__.py $TMP_DIR/get_job_status/storage/ 2>/dev/null || true

# Install dependencies
pip install -r lambda_functions/get_job_status/requirements.txt -t $TMP_DIR/get_job_status/ --quiet

# Create zip
cd $TMP_DIR/get_job_status
zip -r ../get_job_status.zip . -q
cd - > /dev/null

echo "  ✓ get_job_status packaged"

echo ""
echo "3. Deploying Lambda functions..."

# Deploy submit_job
echo "  Deploying submit_job..."
if aws lambda get-function --function-name submit-job --region ${AWS_REGION} >/dev/null 2>&1; then
    # Function exists - update it
    echo "    Updating existing function..."
    aws lambda update-function-code \
      --function-name submit-job \
      --zip-file fileb://$TMP_DIR/submit_job.zip \
      --region ${AWS_REGION} > /dev/null
    
    # Wait for update to complete
    echo "    Waiting for function to be ready..."
    aws lambda wait function-updated --function-name submit-job --region ${AWS_REGION} 2>/dev/null || sleep 5
    
    # Update configuration (AWS_REGION is reserved, don't set it)
    aws lambda update-function-configuration \
      --function-name submit-job \
      --environment "Variables={
        DYNAMODB_TABLE=${DYNAMODB_TABLE_NAME},
        ECS_CLUSTER=${ECS_CLUSTER_NAME},
        SUBNET_ID=${SUBNET_ID},
        S3_BUCKET_NAME=${S3_BUCKET_NAME}
      }" \
      --region ${AWS_REGION} > /dev/null
else
    # Function doesn't exist - create it
    echo "    Creating new function..."
    aws lambda create-function \
      --function-name submit-job \
      --runtime python3.9 \
      --role "$LAMBDA_ROLE_ARN" \
      --handler handler.lambda_handler \
      --zip-file fileb://$TMP_DIR/submit_job.zip \
      --timeout 300 \
      --environment "Variables={
        DYNAMODB_TABLE=${DYNAMODB_TABLE_NAME},
        ECS_CLUSTER=${ECS_CLUSTER_NAME},
        SUBNET_ID=${SUBNET_ID},
        S3_BUCKET_NAME=${S3_BUCKET_NAME}
      }" \
      --region ${AWS_REGION} > /dev/null
    
    # Wait for function to be active
    echo "    Waiting for function to be ready..."
    aws lambda wait function-active --function-name submit-job --region ${AWS_REGION} 2>/dev/null || sleep 10
fi

echo "  ✓ submit_job deployed"

# Deploy get_job_status
echo "  Deploying get_job_status..."
if aws lambda get-function --function-name get-job-status --region ${AWS_REGION} >/dev/null 2>&1; then
    # Function exists - update it
    echo "    Updating existing function..."
    aws lambda update-function-code \
      --function-name get-job-status \
      --zip-file fileb://$TMP_DIR/get_job_status.zip \
      --region ${AWS_REGION} > /dev/null
    
    # Wait for update to complete
    echo "    Waiting for function to be ready..."
    aws lambda wait function-updated --function-name get-job-status --region ${AWS_REGION} 2>/dev/null || sleep 5
    
    # Update configuration
    aws lambda update-function-configuration \
      --function-name get-job-status \
      --environment "Variables={
        DYNAMODB_TABLE=${DYNAMODB_TABLE_NAME}
      }" \
      --region ${AWS_REGION} > /dev/null
else
    # Function doesn't exist - create it
    echo "    Creating new function..."
    aws lambda create-function \
      --function-name get-job-status \
      --runtime python3.9 \
      --role "$LAMBDA_ROLE_ARN" \
      --handler handler.lambda_handler \
      --zip-file fileb://$TMP_DIR/get_job_status.zip \
      --timeout 30 \
      --environment "Variables={
        DYNAMODB_TABLE=${DYNAMODB_TABLE_NAME}
      }" \
      --region ${AWS_REGION} > /dev/null
    
    # Wait for function to be active
    echo "    Waiting for function to be ready..."
    aws lambda wait function-active --function-name get-job-status --region ${AWS_REGION} 2>/dev/null || sleep 10
fi

echo "  ✓ get_job_status deployed"

echo ""
echo "========================================="
echo "✓ Lambda functions deployed!"
echo "========================================="
echo ""
echo "Function ARNs:"
SUBMIT_ARN=$(aws lambda get-function --function-name submit-job --query 'Configuration.FunctionArn' --output text --region ${AWS_REGION})
STATUS_ARN=$(aws lambda get-function --function-name get-job-status --query 'Configuration.FunctionArn' --output text --region ${AWS_REGION})
echo "  submit-job: $SUBMIT_ARN"
echo "  get-job-status: $STATUS_ARN"

