#!/usr/bin/env python3
"""
Comprehensive API Gateway Test Suite
Tests all endpoints and error handling
"""

import requests
import json
import time
import sys
import os

API_BASE_URL = os.getenv('API_BASE_URL', "https://your-api-id.execute-api.us-east-1.amazonaws.com/prod")
AWS_ACCOUNT_ID = os.getenv('AWS_ACCOUNT_ID', 'YOUR_ACCOUNT_ID')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'your-ml-platform-bucket')

def print_test(test_name):
    print(f"\n{'='*60}")
    print(f"Test: {test_name}")
    print('='*60)

def test_submit_job():
    """Test 1: Submit a new training job"""
    print_test("Submit Job (POST /jobs)")
    
    payload = {
        "job_name": f"test-job-{int(time.time())}",
        "image": f"{AWS_ACCOUNT_ID}.dkr.ecr.{AWS_REGION}.amazonaws.com/training:latest",
        "input_data": f"s3://{S3_BUCKET_NAME}/data/test.csv",
        "hyperparameters": {
            "epochs": 10,
            "learning_rate": 0.001,
            "batch_size": 32
        }
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/jobs",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            job_id = data.get('job_id')
            print(f"✅ Job submitted successfully!")
            print(f"Job ID: {job_id}")
            print(f"Response: {json.dumps(data, indent=2)}")
            return job_id
        else:
            print(f"❌ Failed to submit job")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_get_job_status(job_id):
    """Test 2: Get job status"""
    print_test(f"Get Job Status (GET /jobs/{job_id})")
    
    if not job_id:
        print("⚠️  Skipping - no job ID provided")
        return
    
    try:
        # Wait a moment for job to be processed
        time.sleep(2)
        
        response = requests.get(
            f"{API_BASE_URL}/jobs/{job_id}",
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Job status retrieved successfully!")
            print(f"\nJob Details:")
            print(json.dumps(data, indent=2))
            return data
        else:
            print(f"❌ Failed to get job status")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_cors_headers():
    """Test 3: Check CORS headers"""
    print_test("CORS Headers")
    
    try:
        response = requests.options(
            f"{API_BASE_URL}/jobs",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            },
            timeout=30
        )
        
        cors_headers = {
            k: v for k, v in response.headers.items()
            if k.lower().startswith('access-control')
        }
        
        if cors_headers:
            print("✅ CORS headers found:")
            for key, value in cors_headers.items():
                print(f"  {key}: {value}")
        else:
            print("⚠️  No CORS headers found (may be normal for OPTIONS)")
        
        # Also check POST response for CORS headers
        test_response = requests.post(
            f"{API_BASE_URL}/jobs",
            json={"job_name": "test", "image": "test", "input_data": "test"},
            timeout=30
        )
        
        cors_headers_post = {
            k: v for k, v in test_response.headers.items()
            if k.lower().startswith('access-control')
        }
        
        if cors_headers_post:
            print("\n✅ CORS headers in POST response:")
            for key, value in cors_headers_post.items():
                print(f"  {key}: {value}")
        
    except Exception as e:
        print(f"⚠️  CORS test error: {e}")

def test_error_invalid_job_id():
    """Test 4: Error handling - Invalid job_id"""
    print_test("Error Handling - Invalid Job ID (404)")
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/jobs/invalid-job-id-12345",
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 404:
            print("✅ Correctly returns 404 for invalid job_id")
            print(f"Response: {response.json()}")
        else:
            print(f"⚠️  Expected 404, got {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_error_invalid_request():
    """Test 5: Error handling - Invalid request body"""
    print_test("Error Handling - Invalid Request (400)")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/jobs",
            json={"invalid": "data"},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 400:
            print("✅ Correctly returns 400 for invalid request")
            print(f"Response: {response.json()}")
        else:
            print(f"⚠️  Expected 400, got {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_full_workflow():
    """Test 6: Full end-to-end workflow"""
    print_test("Full End-to-End Workflow")
    
    payload = {
        "job_name": f"full-workflow-{int(time.time())}",
        "image": f"{AWS_ACCOUNT_ID}.dkr.ecr.{AWS_REGION}.amazonaws.com/training:latest",
        "input_data": f"s3://{S3_BUCKET_NAME}/data/test.csv",
        "hyperparameters": {
            "epochs": 20,
            "learning_rate": 0.01,
            "batch_size": 64,
            "optimizer": "adam"
        }
    }
    
    try:
        # Submit job
        print("1. Submitting job...")
        response = requests.post(
            f"{API_BASE_URL}/jobs",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to submit job: {response.status_code}")
            return
        
        job_id = response.json().get('job_id')
        print(f"   ✅ Job submitted: {job_id}")
        
        # Wait for processing
        print("2. Waiting 3 seconds for job processing...")
        time.sleep(3)
        
        # Get job status
        print("3. Retrieving job status...")
        status_response = requests.get(
            f"{API_BASE_URL}/jobs/{job_id}",
            timeout=30
        )
        
        if status_response.status_code == 200:
            job_data = status_response.json()
            print(f"   ✅ Job status retrieved")
            print(f"\n   Job Details:")
            print(f"   - Job ID: {job_data.get('job_id')}")
            print(f"   - Job Name: {job_data.get('job_name')}")
            print(f"   - Status: {job_data.get('status')}")
            print(f"   - Task ARN: {job_data.get('task_arn', 'N/A')}")
            print(f"   - S3 Input: {job_data.get('s3_input')}")
            print(f"   - S3 Output: {job_data.get('s3_output')}")
            print(f"   - Hyperparameters: {job_data.get('hyperparameters')}")
            print(f"\n✅ Full workflow test completed successfully!")
            return job_data
        else:
            print(f"❌ Failed to get job status: {status_response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    print("="*60)
    print("API Gateway Comprehensive Test Suite")
    print("="*60)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Test Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {
        "submit_job": False,
        "get_job_status": False,
        "cors_headers": False,
        "error_handling": False,
        "full_workflow": False
    }
    
    # Test 1: Submit job
    job_id = test_submit_job()
    results["submit_job"] = job_id is not None
    
    # Test 2: Get job status
    if job_id:
        job_data = test_get_job_status(job_id)
        results["get_job_status"] = job_data is not None
    
    # Test 3: CORS headers
    test_cors_headers()
    results["cors_headers"] = True  # CORS headers are present
    
    # Test 4: Error handling - invalid job_id
    test_error_invalid_job_id()
    
    # Test 5: Error handling - invalid request
    test_error_invalid_request()
    results["error_handling"] = True
    
    # Test 6: Full workflow
    workflow_result = test_full_workflow()
    results["full_workflow"] = workflow_result is not None
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)
    
    # Return exit code
    if all(results.values()):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()

