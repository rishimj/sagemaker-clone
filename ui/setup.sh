#!/bin/bash
set -e

echo "========================================="
echo "Setting up ML Platform UI"
echo "========================================="
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed"
    echo "Please install Python 3.7 or higher"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.7"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Error: Python 3.7 or higher is required"
    echo "Current version: $PYTHON_VERSION"
    exit 1
fi

echo "✓ Python version: $(python3 --version)"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
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
echo "✓ Setup complete!"
echo "========================================="
echo ""
echo "To start the server, run:"
echo "  ./start.sh"
echo ""
echo "Or manually:"
echo "  source venv/bin/activate"
echo "  python app.py"
echo ""

