#!/bin/bash
# Check Lambda function status and wait if needed

FUNCTION_NAME=$1
REGION=${AWS_REGION:-us-east-1}

if [ -z "$FUNCTION_NAME" ]; then
    echo "Usage: $0 <function-name>"
    exit 1
fi

echo "Checking status of Lambda function: $FUNCTION_NAME"

# Check if function exists
if ! aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" >/dev/null 2>&1; then
    echo "  Function does not exist"
    exit 1
fi

# Get function state
STATE=$(aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" --query 'Configuration.State' --output text 2>/dev/null)

echo "  Current state: $STATE"

if [ "$STATE" == "Pending" ]; then
    echo "  Function is still being created. Waiting..."
    aws lambda wait function-active --function-name "$FUNCTION_NAME" --region "$REGION"
    echo "  ✓ Function is now active"
elif [ "$STATE" == "Active" ]; then
    echo "  ✓ Function is active"
else
    echo "  Function state: $STATE"
fi

