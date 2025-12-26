#!/bin/bash
# Run e2e test with unbuffered output for real-time streaming

set -e

echo "========================================="
echo "Running E2E Test with Real-Time Output"
echo "========================================="
echo ""

# Use Python with unbuffered flag for real-time output
python3 -u tests/test_e2e_with_updates.py

