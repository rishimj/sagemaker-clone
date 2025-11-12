#!/bin/bash
# Don't use set -e, we want to capture exit codes properly
set +e

echo "============================================================"
echo "Wrapper script starting"
echo "============================================================"
echo "Date: $(date)"
echo "Working directory: $(pwd)"
echo "Python version: $(python3 --version)"
echo "Script path: $0"
echo "User: $(whoami)"
echo "Environment:"
env | grep -E "(JOB_ID|S3_|DYNAMODB|AWS_|HYPERPARAMS)" || echo "No relevant env vars found"
echo "============================================================"

# Force unbuffered output
export PYTHONUNBUFFERED=1

# Test Python works
echo "Testing Python..."
python3 -c "import sys; print('Python works'); sys.exit(0)"
PYTHON_TEST=$?
if [ $PYTHON_TEST -ne 0 ]; then
    echo "ERROR: Python test failed with code: $PYTHON_TEST"
    exit 1
fi

# Test import
echo "Testing import..."
python3 -c "import sys; sys.path.insert(0, '/app'); from storage.logger import get_logger; print('Import works')"
IMPORT_TEST=$?
if [ $IMPORT_TEST -ne 0 ]; then
    echo "ERROR: Import test failed with code: $IMPORT_TEST"
    exit 1
fi

# Run training script
echo "Running train.py..."
python3 -u train.py
EXIT_CODE=$?

echo "============================================================"
echo "Training script exited with code: $EXIT_CODE"
echo "============================================================"

# Ensure exit code is valid (0-255)
if [ $EXIT_CODE -lt 0 ]; then
    echo "WARNING: Negative exit code $EXIT_CODE, using 1"
    exit 1
elif [ $EXIT_CODE -gt 255 ]; then
    echo "WARNING: Exit code $EXIT_CODE > 255, using 255"
    exit 255
fi

exit $EXIT_CODE
