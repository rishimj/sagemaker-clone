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
echo "Setting up API Gateway"
echo "========================================="
echo ""

# Get account ID if not set
if [ -z "$AWS_ACCOUNT_ID" ]; then
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
fi

REGION=${AWS_REGION:-us-east-1}
API_NAME="ml-platform-api"

# Lambda function ARNs
SUBMIT_LAMBDA_ARN="arn:aws:lambda:${REGION}:${AWS_ACCOUNT_ID}:function:submit-job"
STATUS_LAMBDA_ARN="arn:aws:lambda:${REGION}:${AWS_ACCOUNT_ID}:function:get-job-status"

echo "1. Creating REST API..."

# Create REST API
API_ID=$(aws apigateway create-rest-api \
    --name "$API_NAME" \
    --description "ML Platform API for training jobs" \
    --region "$REGION" \
    --endpoint-configuration types=REGIONAL \
    --query 'id' \
    --output text 2>/dev/null)

if [ -z "$API_ID" ] || [ "$API_ID" == "None" ]; then
    # API might already exist, try to get it
    API_ID=$(aws apigateway get-rest-apis \
        --region "$REGION" \
        --query "items[?name=='$API_NAME'].id" \
        --output text)
    
    if [ -z "$API_ID" ] || [ "$API_ID" == "None" ]; then
        echo "  ✗ Error: Could not create or find API"
        exit 1
    else
        echo "  API already exists: $API_ID"
    fi
else
    echo "  ✓ API created: $API_ID"
fi

echo ""
echo "2. Getting root resource ID..."

# Get root resource ID
ROOT_RESOURCE_ID=$(aws apigateway get-resources \
    --rest-api-id "$API_ID" \
    --region "$REGION" \
    --query 'items[?path==`/`].id' \
    --output text)

echo "  Root resource ID: $ROOT_RESOURCE_ID"

echo ""
echo "3. Creating /jobs resource..."

# Create /jobs resource
JOBS_RESOURCE_ID=$(aws apigateway create-resource \
    --rest-api-id "$API_ID" \
    --parent-id "$ROOT_RESOURCE_ID" \
    --path-part "jobs" \
    --region "$REGION" \
    --query 'id' \
    --output text 2>/dev/null || \
    aws apigateway get-resources \
        --rest-api-id "$API_ID" \
        --region "$REGION" \
        --query "items[?path=='/jobs'].id" \
        --output text)

if [ -z "$JOBS_RESOURCE_ID" ] || [ "$JOBS_RESOURCE_ID" == "None" ]; then
    echo "  ✗ Error: Could not create /jobs resource"
    exit 1
fi

echo "  ✓ /jobs resource created: $JOBS_RESOURCE_ID"

echo ""
echo "4. Creating POST method for /jobs..."

# Create POST method for /jobs
aws apigateway put-method \
    --rest-api-id "$API_ID" \
    --resource-id "$JOBS_RESOURCE_ID" \
    --http-method POST \
    --authorization-type NONE \
    --region "$REGION" \
    --no-api-key-required \
    > /dev/null 2>&1 || echo "  POST method may already exist"

# Set up Lambda integration for POST
aws apigateway put-integration \
    --rest-api-id "$API_ID" \
    --resource-id "$JOBS_RESOURCE_ID" \
    --http-method POST \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri "arn:aws:apigateway:${REGION}:lambda:path/2015-03-31/functions/${SUBMIT_LAMBDA_ARN}/invocations" \
    --region "$REGION" \
    > /dev/null 2>&1 || echo "  Integration may already exist"

echo "  ✓ POST method configured for /jobs"

echo ""
echo "5. Creating /jobs/{job_id} resource..."

# Create /jobs/{job_id} resource
JOB_ID_RESOURCE_ID=$(aws apigateway create-resource \
    --rest-api-id "$API_ID" \
    --parent-id "$JOBS_RESOURCE_ID" \
    --path-part "{job_id}" \
    --region "$REGION" \
    --query 'id' \
    --output text 2>/dev/null || \
    aws apigateway get-resources \
        --rest-api-id "$API_ID" \
        --region "$REGION" \
        --query "items[?path=='/jobs/{job_id}'].id" \
        --output text)

if [ -z "$JOB_ID_RESOURCE_ID" ] || [ "$JOB_ID_RESOURCE_ID" == "None" ]; then
    echo "  ✗ Error: Could not create /jobs/{job_id} resource"
    exit 1
fi

echo "  ✓ /jobs/{job_id} resource created: $JOB_ID_RESOURCE_ID"

echo ""
echo "6. Creating GET method for /jobs/{job_id}..."

# Create GET method for /jobs/{job_id}
aws apigateway put-method \
    --rest-api-id "$API_ID" \
    --resource-id "$JOB_ID_RESOURCE_ID" \
    --http-method GET \
    --authorization-type NONE \
    --region "$REGION" \
    --no-api-key-required \
    > /dev/null 2>&1 || echo "  GET method may already exist"

# Set up Lambda integration for GET
aws apigateway put-integration \
    --rest-api-id "$API_ID" \
    --resource-id "$JOB_ID_RESOURCE_ID" \
    --http-method GET \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri "arn:aws:apigateway:${REGION}:lambda:path/2015-03-31/functions/${STATUS_LAMBDA_ARN}/invocations" \
    --region "$REGION" \
    > /dev/null 2>&1 || echo "  Integration may already exist"

echo "  ✓ GET method configured for /jobs/{job_id}"

echo ""
echo "7. Adding Lambda permissions for API Gateway..."

# Add permission for submit-job Lambda
aws lambda add-permission \
    --function-name submit-job \
    --statement-id apigateway-invoke-submit \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:${REGION}:${AWS_ACCOUNT_ID}:${API_ID}/*/*" \
    --region "$REGION" \
    > /dev/null 2>&1 || echo "  Permission for submit-job may already exist"

# Add permission for get-job-status Lambda
aws lambda add-permission \
    --function-name get-job-status \
    --statement-id apigateway-invoke-status \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:${REGION}:${AWS_ACCOUNT_ID}:${API_ID}/*/*" \
    --region "$REGION" \
    > /dev/null 2>&1 || echo "  Permission for get-job-status may already exist"

echo "  ✓ Lambda permissions added"

echo ""
echo "8. Deploying API..."

# Deploy API
aws apigateway create-deployment \
    --rest-api-id "$API_ID" \
    --stage-name prod \
    --region "$REGION" \
    > /dev/null 2>&1 || \
aws apigateway create-deployment \
    --rest-api-id "$API_ID" \
    --stage-name prod \
    --region "$REGION" \
    --description "Updated deployment" \
    > /dev/null 2>&1 || echo "  Deployment may already exist"

echo "  ✓ API deployed to 'prod' stage"

echo ""
echo "========================================="
echo "✓ API Gateway setup complete!"
echo "========================================="
echo ""
echo "API Endpoint: https://${API_ID}.execute-api.${REGION}.amazonaws.com/prod"
echo ""
echo "Endpoints:"
echo "  POST https://${API_ID}.execute-api.${REGION}.amazonaws.com/prod/jobs"
echo "  GET  https://${API_ID}.execute-api.${REGION}.amazonaws.com/prod/jobs/{job_id}"
echo ""
echo "Update your .env file with:"
echo "  API_BASE_URL=https://${API_ID}.execute-api.${REGION}.amazonaws.com/prod"
echo ""
echo "API ID: $API_ID"

