"""
Enhanced end-to-end test with better error reporting and ECS task monitoring
"""

import os
import sys
import time
import json
import boto3
import requests
from decimal import Decimal
from datetime import datetime

# Force unbuffered output for real-time streaming
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(line_buffering=True)

from dotenv import load_dotenv
load_dotenv()

API_BASE_URL = os.getenv('API_BASE_URL', 'https://your-api-id.execute-api.us-east-1.amazonaws.com/prod')
S3_BUCKET = os.getenv('S3_BUCKET_NAME', 'your-ml-platform-bucket')
DYNAMODB_TABLE = os.getenv('DYNAMODB_TABLE_NAME', 'ml-jobs')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
ECS_CLUSTER = os.getenv('ECS_CLUSTER_NAME', 'training-cluster')

s3_client = boto3.client('s3', region_name=AWS_REGION)
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
ecs_client = boto3.client('ecs', region_name=AWS_REGION)
logs_client = boto3.client('logs', region_name=AWS_REGION)

def print_step(step_num, total_steps, message):
    print(f"\n{'='*60}", flush=True)
    print(f"Step {step_num}/{total_steps}: {message}", flush=True)
    print(f"{'='*60}", flush=True)

def print_status(message, status="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    icons = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WAIT": "⏳", "WARNING": "⚠️"}
    icon = icons.get(status, "ℹ️")
    print(f"[{timestamp}] {icon} {message}", flush=True)

def create_test_data():
    print_status("Creating test data file...", "INFO")
    test_data = "x,y\n"
    for i in range(1, 101):
        x, y = float(i), 2 * float(i) + 1
        test_data += f"{x},{y}\n"
    
    test_data_key = "data/test_data.csv"
    s3_client.put_object(Bucket=S3_BUCKET, Key=test_data_key, Body=test_data.encode('utf-8'))
    s3_path = f"s3://{S3_BUCKET}/{test_data_key}"
    print_status(f"Test data uploaded to {s3_path}", "SUCCESS")
    return s3_path

def submit_job(job_name, image, data_path, epochs=5, lr=0.01):
    print_status(f"Submitting training job: {job_name}", "INFO")
    payload = {
        "job_name": job_name,
        "image": image,
        "input_data": data_path,
        "hyperparameters": {"epochs": epochs, "learning_rate": lr}
    }
    
    response = requests.post(f"{API_BASE_URL}/jobs", json=payload, headers={"Content-Type": "application/json"})
    if response.status_code != 200:
        print_status(f"Error submitting job: {response.text}", "ERROR")
        return None
    
    result = response.json()
    job_id = result.get('job_id')
    print_status(f"Job submitted! Job ID: {job_id}", "SUCCESS")
    return job_id

def get_job_status(job_id):
    response = requests.get(f"{API_BASE_URL}/jobs/{job_id}")
    return response.json() if response.status_code == 200 else None

def check_ecs_task_status(task_arn):
    """Check ECS task status directly"""
    try:
        task_id = task_arn.split('/')[-1]
        response = ecs_client.describe_tasks(cluster=ECS_CLUSTER, tasks=[task_id])
        if response['tasks']:
            task = response['tasks'][0]
            status = task['lastStatus']
            desired_status = task['desiredStatus']
            
            # Check for stopped reason
            stopped_reason = task.get('stoppedReason', '')
            if stopped_reason:
                print_status(f"Task stopped reason: {stopped_reason}", "WARNING")
            
            # Check container status
            if task.get('containers'):
                container = task['containers'][0]
                if 'reason' in container:
                    print_status(f"Container reason: {container['reason']}", "WARNING")
                if 'exitCode' in container:
                    print_status(f"Container exit code: {container.get('exitCode')}", "WARNING")
            
            return {
                'status': status,
                'desired_status': desired_status,
                'stopped_reason': stopped_reason,
                'task': task
            }
    except Exception as e:
        print_status(f"Error checking ECS task: {e}", "ERROR")
    return None

def wait_for_job_completion(job_id, max_wait_time=600, poll_interval=10):
    print_status(f"Waiting for job {job_id} to complete (max {max_wait_time}s)...", "WAIT")
    start_time = time.time()
    last_status = None
    task_arn = None
    last_elapsed = -1
    
    while time.time() - start_time < max_wait_time:
        status = get_job_status(job_id)
        if not status:
            print_status("Failed to get job status", "ERROR")
            return None
        
        current_status = status.get('status', 'unknown')
        current_task_arn = status.get('task_arn')
        elapsed = int(time.time() - start_time)
        
        if current_status != last_status:
            print()  # New line when status changes
            print_status(f"Job status: {current_status}", "INFO")
            last_status = current_status
        
        if current_task_arn and current_task_arn != task_arn:
            task_arn = current_task_arn
            print_status(f"ECS Task ARN: {task_arn}", "INFO")
            
            # Check ECS task status
            task_info = check_ecs_task_status(task_arn)
            if task_info:
                print_status(f"ECS Task Status: {task_info['status']} (desired: {task_info['desired_status']})", "INFO")
        
        if current_status in ['completed', 'failed']:
            print()  # New line before final status
            print_status(f"Job finished: {current_status} ({elapsed}s)", 
                        "SUCCESS" if current_status == 'completed' else "ERROR")
            return status
        
        # Print progress every 10 seconds or when status changes
        if elapsed != last_elapsed and elapsed % 10 == 0:
            print(f"\n  ⏳ {elapsed}s elapsed (status: {current_status})", flush=True)
            last_elapsed = elapsed
        elif elapsed != last_elapsed:
            print(f"  ... {elapsed}s elapsed (status: {current_status})", end='\r', flush=True)
            last_elapsed = elapsed
        
        time.sleep(poll_interval)
    
    print_status(f"Job did not complete within {max_wait_time}s", "WARNING")
    if task_arn:
        print_status("Checking final ECS task status...", "INFO")
        check_ecs_task_status(task_arn)
    return get_job_status(job_id)

def check_s3_model(job_name):
    print_status("Checking for model artifacts in S3...", "INFO")
    model_prefix = f"models/{job_name}/"
    try:
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix=model_prefix)
        if 'Contents' in response:
            files = [obj['Key'] for obj in response['Contents']]
            print_status(f"Found {len(files)} file(s) in S3:", "SUCCESS")
            for file in files:
                print(f"  - {file}", flush=True)
            return True
        else:
            print_status(f"No files found at s3://{S3_BUCKET}/{model_prefix}", "WARNING")
            return False
    except Exception as e:
        print_status(f"Error checking S3: {e}", "ERROR")
        return False

def test_end_to_end():
    print("\n" + "="*60, flush=True)
    print("🚀 ML Platform End-to-End Test (Enhanced)", flush=True)
    print("="*60, flush=True)
    
    total_steps = 5
    job_name = f"e2e-test-{int(time.time())}"
    account_id = os.getenv('AWS_ACCOUNT_ID', 'YOUR_ACCOUNT_ID')
    image = f"{account_id}.dkr.ecr.{AWS_REGION}.amazonaws.com/training:latest"
    
    try:
        print_step(1, total_steps, "Creating test data")
        data_path = create_test_data()
        
        print_step(2, total_steps, "Submitting training job")
        job_id = submit_job(job_name=job_name, image=image, data_path=data_path, epochs=5, lr=0.01)
        if not job_id:
            return False
        
        # Wait a moment for task to start
        print_status("Waiting 5 seconds for ECS task to start...", "WAIT")
        time.sleep(5)
        
        # Check initial job status
        initial_status = get_job_status(job_id)
        if initial_status:
            print_status(f"Initial job status: {initial_status.get('status')}", "INFO")
            if 'task_arn' in initial_status:
                print_status(f"Task ARN: {initial_status['task_arn']}", "INFO")
                check_ecs_task_status(initial_status['task_arn'])
            else:
                print_status("⚠️  No task_arn found - ECS task may not have started", "WARNING")
        
        print_step(3, total_steps, "Monitoring job execution")
        final_status = wait_for_job_completion(job_id, max_wait_time=600)
        
        print_step(4, total_steps, "Verifying results")
        job_status = final_status.get('status') if final_status else 'unknown'
        print_status(f"Final job status: {job_status}", "SUCCESS" if job_status == 'completed' else "ERROR")
        
        model_exists = check_s3_model(job_name)
        
        print_step(5, total_steps, "Test Summary")
        print(f"Job ID: {job_id}", flush=True)
        print(f"Job Name: {job_name}", flush=True)
        print(f"Final Status: {job_status}", flush=True)
        print(f"Model in S3: {'Yes' if model_exists else 'No'}", flush=True)
        
        success = job_status == 'completed' and model_exists
        print_status("✅ Test PASSED!" if success else "❌ Test FAILED", "SUCCESS" if success else "ERROR")
        return success
        
    except Exception as e:
        print_status(f"Test failed: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    # Force unbuffered output
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    
    print("="*60, flush=True)
    print("Starting E2E Test...", flush=True)
    print("="*60, flush=True)
    
    try:
        success = test_end_to_end()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user", flush=True)
        exit(130)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        exit(1)

