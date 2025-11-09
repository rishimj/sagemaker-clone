#!/bin/bash
set -e

echo "========================================="
echo "AWS CLI Admin Setup Helper"
echo "========================================="
echo ""
echo "This script helps you configure AWS CLI with admin credentials."
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed!"
    echo ""
    echo "Install it with:"
    echo "  brew install awscli  # macOS"
    echo "  or"
    echo "  pip install awscli"
    echo ""
    exit 1
fi

echo "✓ AWS CLI is installed"
echo ""

# Check current configuration
echo "Current AWS configuration:"
if [ -f ~/.aws/credentials ]; then
    echo "  ✓ Credentials file exists: ~/.aws/credentials"
    if [ -f ~/.aws/config ]; then
        echo "  ✓ Config file exists: ~/.aws/config"
        echo ""
        echo "Current profile:"
        aws configure list 2>/dev/null || echo "  (No default profile configured)"
    else
        echo "  ⚠ Config file missing"
    fi
else
    echo "  ⚠ No credentials file found"
    echo "  You'll need to configure AWS CLI"
fi

echo ""
echo "========================================="
echo "Setup Options"
echo "========================================="
echo ""
echo "1. Configure AWS CLI with new credentials"
echo "2. Check current AWS identity"
echo "3. Grant admin access to current user"
echo "4. Test admin access"
echo ""
read -p "Choose an option (1-4): " option

case $option in
    1)
        echo ""
        echo "Configuring AWS CLI..."
        echo ""
        echo "You'll need:"
        echo "  - AWS Access Key ID"
        echo "  - AWS Secret Access Key"
        echo "  - Default region (e.g., us-east-1)"
        echo "  - Default output format (json)"
        echo ""
        echo "Press Enter to continue..."
        read
        
        aws configure
        
        echo ""
        echo "✓ AWS CLI configured!"
        echo ""
        echo "Verifying configuration..."
        aws sts get-caller-identity
        ;;
    2)
        echo ""
        echo "Current AWS Identity:"
        echo ""
        aws sts get-caller-identity || {
            echo "❌ Could not get AWS identity"
            echo "   Make sure AWS CLI is configured: aws configure"
        }
        ;;
    3)
        echo ""
        echo "Granting admin access..."
        ./grant_admin_access.sh
        ;;
    4)
        echo ""
        echo "Testing admin access..."
        echo ""
        
        # Test basic access
        echo "1. Testing basic access..."
        if aws sts get-caller-identity &>/dev/null; then
            echo "   ✓ Basic access works"
        else
            echo "   ❌ Basic access failed"
            exit 1
        fi
        
        # Test IAM access
        echo "2. Testing IAM access..."
        if aws iam list-users &>/dev/null; then
            echo "   ✓ IAM access works (you have admin access!)"
        else
            echo "   ⚠ IAM access limited (may not have admin access)"
            echo "   Run: ./grant_admin_access.sh"
        fi
        
        # Test EC2 access
        echo "3. Testing EC2 access..."
        if aws ec2 describe-vpcs &>/dev/null; then
            echo "   ✓ EC2 access works"
        else
            echo "   ⚠ EC2 access limited"
        fi
        
        echo ""
        echo "✓ Access test complete!"
        ;;
    *)
        echo "Invalid option"
        exit 1
        ;;
esac

echo ""
echo "========================================="
echo "Next Steps"
echo "========================================="
echo ""
echo "If you have admin access, you can now:"
echo "  1. Run: ./infrastructure/setup_all.sh"
echo "  2. Run: ./infrastructure/setup_all_permissions.sh"
echo "  3. Continue with your ML platform setup"
echo ""
echo "See GRANT_ADMIN_ACCESS.md for more information."

