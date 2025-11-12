#!/usr/bin/env python3
import sys
import os

print("="*60, flush=True)
print("Minimal test script", flush=True)
print(f"Python version: {sys.version}", flush=True)
print(f"Working directory: {os.getcwd()}", flush=True)
print("="*60, flush=True)

print("✅ Script completed successfully", flush=True)
sys.exit(0)
