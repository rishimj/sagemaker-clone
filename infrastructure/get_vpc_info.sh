#!/bin/bash
set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    AWS_REGION=${AWS_REGION:-us-east-1}
fi

echo "Getting VPC and Subnet Information..."
echo ""

# Get default VPC
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query "Vpcs[0].VpcId" \
  --output text \
  --region ${AWS_REGION})

if [ "$VPC_ID" == "None" ] || [ -z "$VPC_ID" ]; then
    echo "Error: No default VPC found"
    echo "Please create a VPC or specify a VPC ID manually"
    exit 1
fi

echo "Default VPC ID: $VPC_ID"

# Get a subnet in the default VPC
SUBNET_ID=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query "Subnets[0].SubnetId" \
  --output text \
  --region ${AWS_REGION})

if [ "$SUBNET_ID" == "None" ] || [ -z "$SUBNET_ID" ]; then
    echo "Error: No subnet found in default VPC"
    exit 1
fi

echo "Subnet ID: $SUBNET_ID"

# Get security group
SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=group-name,Values=default" \
  --query "SecurityGroups[0].GroupId" \
  --output text \
  --region ${AWS_REGION})

echo "Security Group ID: $SG_ID"
echo ""
echo "Add these to your .env file:"
echo "SUBNET_ID=$SUBNET_ID"
echo "SECURITY_GROUP_ID=$SG_ID"

