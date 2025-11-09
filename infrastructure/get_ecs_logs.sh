#!/bin/bash
set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

AWS_REGION=${AWS_REGION:-us-east-1}
LOG_GROUP="/ecs/training-job"

echo "========================================="
echo "Getting ECS CloudWatch Logs"
echo "========================================="
echo ""

# Check if log group exists
echo "1. Checking if log group exists: $LOG_GROUP"
if aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" --region $AWS_REGION --query 'logGroups[?logGroupName==`'$LOG_GROUP'`]' --output text 2>&1 | grep -q "$LOG_GROUP"; then
    echo "   ✅ Log group exists"
else
    echo "   ❌ Log group does not exist"
    echo "   Creating log group..."
    aws logs create-log-group --log-group-name "$LOG_GROUP" --region $AWS_REGION 2>&1 || echo "   ⚠️  Could not create log group (may need permissions)"
fi

echo ""
echo "2. Listing recent log streams..."
LOG_STREAMS=$(aws logs describe-log-streams \
    --log-group-name "$LOG_GROUP" \
    --region $AWS_REGION \
    --order-by LastEventTime \
    --descending \
    --max-items 5 \
    --query 'logStreams[*].logStreamName' \
    --output text 2>&1) || {
    echo "   ❌ Cannot list log streams (permission denied)"
    echo "   💡 Use AWS Console instead:"
    echo "      https://console.aws.amazon.com/ecs/v2/clusters/training-cluster/tasks"
    echo "   Or:"
    echo "      https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/$252Fecs$252Ftraining-job"
    exit 1
}

if [ -z "$LOG_STREAMS" ] || [ "$LOG_STREAMS" == "None" ]; then
    echo "   ⚠️  No log streams found"
    echo "   This might mean:"
    echo "     - No tasks have run yet"
    echo "     - Logs haven't been created"
    echo "     - You don't have permissions to read logs"
else
    echo "   Found log streams:"
    for stream in $LOG_STREAMS; do
        echo "     - $stream"
    done
    
    echo ""
    echo "3. Getting logs from most recent stream..."
    LATEST_STREAM=$(echo $LOG_STREAMS | awk '{print $1}')
    echo "   Latest stream: $LATEST_STREAM"
    echo ""
    echo "   ========================================="
    echo "   LOGS FROM: $LATEST_STREAM"
    echo "   ========================================="
    echo ""
    
    aws logs get-log-events \
        --log-group-name "$LOG_GROUP" \
        --log-stream-name "$LATEST_STREAM" \
        --region $AWS_REGION \
        --limit 100 \
        --query 'events[*].message' \
        --output text 2>&1 | head -100
fi

echo ""
echo "========================================="
echo "Done"
echo "========================================="

