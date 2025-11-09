#!/bin/bash
# Generate a unique S3 bucket name

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
TIMESTAMP=$(date +%s | tail -c 6)
USER_NAME=$(whoami | tr '[:upper:]' '[:lower:]')

# Generate unique bucket name
BUCKET_NAME="ml-platform-${ACCOUNT_ID}-${TIMESTAMP}"

echo "Generated unique bucket name: $BUCKET_NAME"
echo ""
echo "To use this bucket name, update your .env file:"
echo "  S3_BUCKET_NAME=$BUCKET_NAME"
echo ""
echo "Or run:"
echo "  sed -i '' 's/S3_BUCKET_NAME=.*/S3_BUCKET_NAME=$BUCKET_NAME/' .env"
echo ""
echo "Then create the bucket:"
echo "  ./infrastructure/create_s3_bucket.sh"

