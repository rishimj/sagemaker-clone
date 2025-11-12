#!/bin/bash
set -e

echo "========================================="
echo "Starting ML Platform UI"
echo "========================================="
echo ""

# Load environment variables
if [ -f ../.env ]; then
    export $(cat ../.env | grep -v '^#' | xargs)
    echo "✓ Loaded environment variables from ../.env"
else
    echo "⚠️  No .env file found. Using defaults or environment variables."
fi

# Set defaults
export AWS_REGION=${AWS_REGION:-us-east-1}
export AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID:-YOUR_ACCOUNT_ID}
export S3_BUCKET_NAME=${S3_BUCKET_NAME:-your-ml-platform-bucket}
export API_BASE_URL=${API_BASE_URL:-https://your-api-id.execute-api.us-east-1.amazonaws.com/prod}
export TRAINING_IMAGE=${TRAINING_IMAGE:-${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/training:latest}
export PORT=${PORT:-8080}

echo ""
echo "Configuration:"
echo "  AWS_REGION: $AWS_REGION"
echo "  S3_BUCKET_NAME: $S3_BUCKET_NAME"
echo "  API_BASE_URL: $API_BASE_URL"
echo "  TRAINING_IMAGE: $TRAINING_IMAGE"
echo "  PORT: $PORT"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip -q

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt
echo "✓ Dependencies installed"

echo ""
echo "========================================="
echo "Starting Flask server..."
echo "========================================="
echo ""
echo "Open your browser and navigate to:"
echo "  http://localhost:$PORT"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run the Flask app
python app.py

