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

echo "Creating ECS Task Definition..."

# Create CloudWatch log group if it doesn't exist
aws logs create-log-group \
  --log-group-name /ecs/training-job \
  --region ${AWS_REGION} 2>/dev/null || echo "Log group already exists"

# Create task definition
cat > /tmp/task-definition.json <<EOF
{
  "family": "training-job",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/MLPlatformECSTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/MLPlatformECSTaskRole",
  "containerDefinitions": [
    {
      "name": "training",
      "image": "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/training:latest",
      "essential": true,
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/training-job",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
EOF

# Register task definition
aws ecs register-task-definition \
  --cli-input-json file:///tmp/task-definition.json \
  --region ${AWS_REGION}

echo "✓ ECS Task Definition created: training-job"

rm /tmp/task-definition.json

