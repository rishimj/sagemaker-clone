#!/bin/bash
# Fix .env file with correct AWS Account ID

ENV_FILE=".env"

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env file not found"
    exit 1
fi

# Get actual AWS Account ID
ACTUAL_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)

if [ -z "$ACTUAL_ACCOUNT_ID" ]; then
    echo "Error: Could not get AWS Account ID. Make sure AWS CLI is configured."
    exit 1
fi

echo "Fixing .env file..."
echo "Current Account ID in .env: $(grep AWS_ACCOUNT_ID $ENV_FILE | cut -d'=' -f2)"
echo "Actual Account ID: $ACTUAL_ACCOUNT_ID"
echo ""

# Update account ID
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/AWS_ACCOUNT_ID=.*/AWS_ACCOUNT_ID=$ACTUAL_ACCOUNT_ID/" "$ENV_FILE"
else
    # Linux
    sed -i "s/AWS_ACCOUNT_ID=.*/AWS_ACCOUNT_ID=$ACTUAL_ACCOUNT_ID/" "$ENV_FILE"
fi

echo "✓ Updated AWS_ACCOUNT_ID to $ACTUAL_ACCOUNT_ID"
echo ""
echo "Updated .env file:"
grep AWS_ACCOUNT_ID "$ENV_FILE"

