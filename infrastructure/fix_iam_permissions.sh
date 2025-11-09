#!/bin/bash
set -e

echo "Adding EC2 permissions to IAM user..."
echo ""

# Get current user
CURRENT_USER=$(aws sts get-caller-identity --query 'Arn' --output text | cut -d'/' -f2)
echo "Current IAM user: $CURRENT_USER"

# Create policy document for EC2 read permissions
cat > /tmp/ec2-read-policy.json <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeVpcs",
                "ec2:DescribeSubnets",
                "ec2:DescribeSecurityGroups",
                "ec2:DescribeAvailabilityZones"
            ],
            "Resource": "*"
        }
    ]
}
EOF

# Check if policy exists
POLICY_NAME="EC2ReadOnlyForMLPlatform"
POLICY_ARN="arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/$POLICY_NAME"

echo "Creating/updating policy: $POLICY_NAME"

# Delete existing policy if it exists (to update it)
aws iam delete-policy --policy-arn "$POLICY_ARN" 2>/dev/null || true
sleep 2

# Create policy
aws iam create-policy \
    --policy-name "$POLICY_NAME" \
    --policy-document file:///tmp/ec2-read-policy.json \
    2>/dev/null || echo "Policy creation failed (may already exist)"

# Attach to user
echo "Attaching policy to user: $CURRENT_USER"
aws iam attach-user-policy \
    --user-name "$CURRENT_USER" \
    --policy-arn "$POLICY_ARN" \
    2>/dev/null || echo "Policy attachment failed (may already be attached)"

echo ""
echo "✓ EC2 permissions added!"
echo ""
echo "Note: It may take a few seconds for permissions to propagate."
echo "Wait 10-15 seconds before running the VPC info script again."

rm /tmp/ec2-read-policy.json

