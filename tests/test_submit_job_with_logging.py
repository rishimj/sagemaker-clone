"""
Test job submission with detailed logging to see what happens
"""

import os
import json
import requests
import time
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv('API_BASE_URL', 'https://your-api-id.execute-api.us-east-1.amazonaws.com/prod')
S3_BUCKET = os.getenv('S3_BUCKET_NAME', 'your-ml-platform-bucket')

print("="*60)
print("Testing Job Submission with Detailed Logging")
print("="*60)

# Submit a job
job_name = f"test-logging-{int(time.time())}"
payload = {
    "job_name": job_name,
    "image": f"{os.getenv('AWS_ACCOUNT_ID', 'YOUR_ACCOUNT_ID')}.dkr.ecr.us-east-1.amazonaws.com/training:latest",
    "input_data": f"s3://{S3_BUCKET}/data/test_data.csv",
    "hyperparameters": {
        "epochs": 5,
        "learning_rate": 0.01
    }
}

print(f"\n1. Submitting job: {job_name}")
print(f"   Payload: {json.dumps(payload, indent=2)}")

response = requests.post(
    f"{API_BASE_URL}/jobs",
    json=payload,
    headers={"Content-Type": "application/json"}
)

print(f"\n2. API Response:")
print(f"   Status Code: {response.status_code}")
print(f"   Response: {response.text}")

if response.status_code == 200:
    result = response.json()
    job_id = result.get('job_id')
    print(f"\n3. Job ID: {job_id}")
    
    # Wait a moment
    print(f"\n4. Waiting 5 seconds for Lambda to process...")
    time.sleep(5)
    
    # Check job status
    print(f"\n5. Checking job status...")
    status_response = requests.get(f"{API_BASE_URL}/jobs/{job_id}")
    if status_response.status_code == 200:
        status = status_response.json()
        print(f"   Job Status: {status.get('status')}")
        print(f"   Task ARN: {status.get('task_arn', 'Not set')}")
        print(f"   Full Status: {json.dumps(status, indent=2, default=str)}")
    else:
        print(f"   Error getting status: {status_response.text}")
else:
    print(f"\n❌ Job submission failed!")

print("\n" + "="*60)
print("Next: Check CloudWatch Logs for /aws/lambda/submit-job")
print("="*60)

