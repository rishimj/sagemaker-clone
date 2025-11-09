#!/bin/bash
set -e

echo "========================================="
echo "Create New IAM User with Admin Access"
echo "========================================="
echo ""
echo "This script creates a new IAM user with AdministratorAccess."
echo "Use this if you have root account access."
echo ""

# Get account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")
if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo "❌ Could not get AWS account ID"
    echo "   Make sure AWS CLI is configured: aws configure"
    exit 1
fi

echo "AWS Account ID: $AWS_ACCOUNT_ID"
echo ""

# Prompt for user name
read -p "Enter username for new admin user (default: ml-platform-admin): " USER_NAME
USER_NAME=${USER_NAME:-ml-platform-admin}

echo ""
echo "Creating user: $USER_NAME"
echo ""

# Create user
if aws iam create-user --user-name "$USER_NAME" 2>/dev/null; then
    echo "✓ User created: $USER_NAME"
else
    echo "⚠ User may already exist, continuing..."
fi

# Attach AdministratorAccess policy
echo "Attaching AdministratorAccess policy..."
if aws iam attach-user-policy \
    --user-name "$USER_NAME" \
    --policy-arn arn:aws:iam::aws:policy/AdministratorAccess; then
    echo "✓ AdministratorAccess policy attached"
else
    echo "❌ Failed to attach policy (you may need root/admin access)"
    exit 1
fi

# Create access key
echo "Creating access key..."
ACCESS_KEY_OUTPUT=$(aws iam create-access-key --user-name "$USER_NAME")
ACCESS_KEY_ID=$(echo "$ACCESS_KEY_OUTPUT" | grep -oP '(?<="AccessKeyId": ")[^"]*')
SECRET_ACCESS_KEY=$(echo "$ACCESS_KEY_OUTPUT" | grep -oP '(?<="SecretAccessKey": ")[^"]*')

if [ -n "$ACCESS_KEY_ID" ] && [ -n "$SECRET_ACCESS_KEY" ]; then
    echo "✓ Access key created"
    echo ""
    echo "========================================="
    echo "✓ Admin User Created Successfully!"
    echo "========================================="
    echo ""
    echo "User Name: $USER_NAME"
    echo "Access Key ID: $ACCESS_KEY_ID"
    echo "Secret Access Key: $SECRET_ACCESS_KEY"
    echo ""
    echo "⚠️  IMPORTANT: Save these credentials securely!"
    echo "   You won't be able to see the secret key again."
    echo ""
    echo "To use this user with AWS CLI:"
    echo "  aws configure"
    echo "  # Enter the Access Key ID and Secret Access Key above"
    echo ""
    echo "Or set environment variables:"
    echo "  export AWS_ACCESS_KEY_ID=$ACCESS_KEY_ID"
    echo "  export AWS_SECRET_ACCESS_KEY=$SECRET_ACCESS_KEY"
    echo ""
    echo "Test the new user:"
    echo "  aws sts get-caller-identity"
    echo ""
else
    echo "❌ Failed to create access key"
    exit 1
fi

