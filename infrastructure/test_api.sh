#!/bin/bash
set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

API_BASE_URL=${API_BASE_URL:-https://your-api-id.execute-api.us-east-1.amazonaws.com/prod}
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID:-YOUR_ACCOUNT_ID}
AWS_REGION=${AWS_REGION:-us-east-1}
S3_BUCKET_NAME=${S3_BUCKET_NAME:-your-ml-platform-bucket}

echo "========================================="
echo "Testing API Gateway Endpoints"
echo "========================================="
echo ""
echo "API Base URL: $API_BASE_URL"
echo ""

# Test 1: Submit a job
echo "1. Testing POST /jobs (Submit Job)..."
echo ""

SUBMIT_PAYLOAD="{
  \"job_name\": \"test-job-api\",
  \"image\": \"${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/training:latest\",
  \"input_data\": \"s3://${S3_BUCKET_NAME}/data/test.csv\",
  \"hyperparameters\": {
    \"epochs\": 10,
    \"learning_rate\": 0.001
  }
}"

RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -d "$SUBMIT_PAYLOAD" \
    "${API_BASE_URL}/jobs")

HTTP_BODY=$(echo "$RESPONSE" | sed -E 's/HTTP_STATUS\:[0-9]{3}$//')
HTTP_STATUS=$(echo "$RESPONSE" | tr -d '\n' | sed -E 's/.*HTTP_STATUS:([0-9]{3})$/\1/')

if [ "$HTTP_STATUS" == "200" ]; then
    echo "  ✓ POST /jobs successful (Status: $HTTP_STATUS)"
    JOB_ID=$(echo "$HTTP_BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('job_id', 'N/A'))" 2>/dev/null || echo "N/A")
    echo "  Response: $HTTP_BODY"
    echo "  Job ID: $JOB_ID"
    
    if [ "$JOB_ID" != "N/A" ] && [ -n "$JOB_ID" ]; then
        echo ""
        echo "2. Testing GET /jobs/{job_id} (Get Job Status)..."
        echo ""
        
        sleep 2  # Wait a moment for DynamoDB to be consistent
        
        STATUS_RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
            -X GET \
            "${API_BASE_URL}/jobs/${JOB_ID}")
        
        STATUS_BODY=$(echo "$STATUS_RESPONSE" | sed -E 's/HTTP_STATUS\:[0-9]{3}$//')
        STATUS_CODE=$(echo "$STATUS_RESPONSE" | tr -d '\n' | sed -E 's/.*HTTP_STATUS:([0-9]{3})$/\1/')
        
        if [ "$STATUS_CODE" == "200" ]; then
            echo "  ✓ GET /jobs/${JOB_ID} successful (Status: $STATUS_CODE)"
            echo "  Response: $STATUS_BODY" | python3 -m json.tool 2>/dev/null || echo "  Response: $STATUS_BODY"
        else
            echo "  ✗ GET /jobs/${JOB_ID} failed (Status: $STATUS_CODE)"
            echo "  Response: $STATUS_BODY"
        fi
    else
        echo "  ⚠ Could not extract job_id from response"
    fi
else
    echo "  ✗ POST /jobs failed (Status: $HTTP_STATUS)"
    echo "  Response: $HTTP_BODY"
fi

echo ""
echo "========================================="
echo "API Gateway Test Complete"
echo "========================================="

