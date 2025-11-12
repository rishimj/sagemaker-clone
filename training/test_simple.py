#!/usr/bin/env python3
"""Simple test script to verify container runs"""
import sys
import os

print("="*60, flush=True)
print("Simple test script starting", flush=True)
print(f"Python version: {sys.version}", flush=True)
print(f"Working directory: {os.getcwd()}", flush=True)
print(f"Python path: {sys.path}", flush=True)
print("="*60, flush=True)

# Test import
try:
    print("Testing storage.logger import...", flush=True)
    sys.path.insert(0, '/app')
    from storage.logger import get_logger
    print("✅ Import successful", flush=True)
except Exception as e:
    print(f"❌ Import failed: {e}", flush=True)
    import traceback
    traceback.print_exc(file=sys.stdout)
    sys.exit(1)

print("="*60, flush=True)
print("✅ Test script completed successfully", flush=True)
print("="*60, flush=True)
sys.exit(0)

