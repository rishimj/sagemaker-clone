"""
End-to-end test for the ML training platform
Tests the complete workflow: submit job -> ECS execution -> model saving -> status updates
"""

import os
import time
import json
import boto3
import requests
from decimal import Decimal
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

API_BASE_URL = os.getenv('API_BASE_URL', 'https://your-api-id.execute-api.us-east-1.amazonaws.com/prod')
S3_BUCKET = os.getenv('S3_BUCKET_NAME', 'your-ml-platform-bucket')
DYNAMODB_TABLE = os.getenv('DYNAMODB_TABLE_NAME', 'ml-jobs')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
ECS_CLUSTER = os.getenv('ECS_CLUSTER_NAME', 'training-cluster')

# Initialize AWS clients
s3_client = boto3.client('s3', region_name=AWS_REGION)
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
ecs_client = boto3.client('ecs', region_name=AWS_REGION)
logs_client = boto3.client('logs', region_name=AWS_REGION)

def print_step(step_num, total_steps, message):
    """Print a formatted step message"""
    print(f"\n{'='*60}")
    print(f"Step {step_num}/{total_steps}: {message}")
    print(f"{'='*60}")

def print_status(message, status="INFO"):
    """Print a status message with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    icons = {
        "INFO": "ℹ️",
        "SUCCESS": "✅",
        "ERROR": "❌",
        "WAIT": "⏳",
        "WARNING": "⚠️"
    }
    icon = icons.get(status, "ℹ️")
    print(f"[{timestamp}] {icon} {message}")

def create_test_data():
    """Create a simple test CSV file and upload to S3"""
    print_status("Creating test data file...", "INFO")
    
    # Create regression test data with features and target
    # Simple relationship: target = 2*feature1 + 1.5*feature2 + 0.5*feature3
    test_data = "feature1,feature2,feature3,target\n"
    for i in range(1, 101):
        feature1 = float(i) * 0.5
        feature2 = float(i) * 1.2
        feature3 = float(i) * 2.1
        target = 2 * feature1 + 1.5 * feature2 + 0.5 * feature3
        test_data += f"{feature1},{feature2},{feature3},{target}\n"
    
    # Upload to S3
    test_data_key = "data/test_data.csv"
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=test_data_key,
        Body=test_data.encode('utf-8')
    )
    
    s3_path = f"s3://{S3_BUCKET}/{test_data_key}"
    print_status(f"Test data uploaded to {s3_path}", "SUCCESS")
    return s3_path

def submit_job(job_name, image, data_path, task_type='regression', algorithm='linear', **kwargs):
    """Submit a training job via API"""
    print_status(f"Submitting training job: {job_name}", "INFO")
    print_status(f"Task type: {task_type}, Algorithm: {algorithm}", "INFO")
    
    # Build hyperparameters
    hyperparameters = {
        "task_type": task_type,
        "algorithm": algorithm,
        "target_column": "target",
        "test_size": 0.2,
        "random_state": 42
    }
    
    # Add algorithm-specific hyperparameters
    if algorithm in ['random_forest', 'gradient_boosting']:
        hyperparameters['n_estimators'] = kwargs.get('n_estimators', 10)
    if 'max_depth' in kwargs:
        hyperparameters['max_depth'] = kwargs['max_depth']
    if 'learning_rate' in kwargs:
        hyperparameters['learning_rate'] = kwargs['learning_rate']
    
    payload = {
        "job_name": job_name,
        "image": image,
        "input_data": data_path,
        "hyperparameters": hyperparameters
    }
    
    response = requests.post(
        f"{API_BASE_URL}/jobs",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        print_status(f"Error submitting job: {response.text}", "ERROR")
        return None
    
    result = response.json()
    job_id = result.get('job_id')
    print_status(f"Job submitted successfully! Job ID: {job_id}", "SUCCESS")
    return job_id

def get_job_status(job_id):
    """Get job status from API"""
    response = requests.get(f"{API_BASE_URL}/jobs/{job_id}")
    
    if response.status_code != 200:
        print_status(f"Error getting job status: {response.text}", "ERROR")
        return None
    
    return response.json()

def wait_for_job_completion(job_id, max_wait_time=600, poll_interval=10):
    """Wait for job to complete, checking status periodically"""
    print_status(f"Waiting for job {job_id} to complete (max {max_wait_time}s)...", "WAIT")
    
    start_time = time.time()
    last_status = None
    
    while time.time() - start_time < max_wait_time:
        status = get_job_status(job_id)
        
        if not status:
            print_status("Failed to get job status", "ERROR")
            return None
        
        current_status = status.get('status', 'unknown')
        
        # Print status update if it changed
        if current_status != last_status:
            print_status(f"Job status: {current_status}", "INFO")
            last_status = current_status
            
            if 'task_arn' in status:
                print_status(f"ECS Task: {status['task_arn']}", "INFO")
        
        # Check if job is complete
        if current_status in ['completed', 'failed']:
            elapsed = int(time.time() - start_time)
            print_status(f"Job finished with status: {current_status} (took {elapsed}s)", 
                        "SUCCESS" if current_status == 'completed' else "ERROR")
            return status
        
        # Wait before next check
        time.sleep(poll_interval)
        elapsed = int(time.time() - start_time)
        print(f"  ... {elapsed}s elapsed", end='\r')
    
    print_status(f"Job did not complete within {max_wait_time}s", "WARNING")
    return get_job_status(job_id)

def check_s3_model(job_name):
    """Check if model was saved to S3"""
    print_status(f"Checking for model artifacts in S3...", "INFO")
    
    model_prefix = f"models/{job_name}/"
    
    try:
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET,
            Prefix=model_prefix
        )
        
        if 'Contents' in response:
            files = [obj['Key'] for obj in response['Contents']]
            print_status(f"Found {len(files)} file(s) in S3:", "SUCCESS")
            for file in files:
                print(f"  - {file}")
            return True
        else:
            print_status(f"No files found at s3://{S3_BUCKET}/{model_prefix}", "WARNING")
            return False
    except Exception as e:
        print_status(f"Error checking S3: {e}", "ERROR")
        return False

def get_ecs_task_logs(task_arn):
    """Get logs from ECS task"""
    print_status(f"Fetching ECS task logs...", "INFO")
    
    try:
        # Extract task ID from ARN
        task_id = task_arn.split('/')[-1]
        
        # Get task details to find log group
        response = ecs_client.describe_tasks(
            cluster=ECS_CLUSTER,
            tasks=[task_id]
        )
        
        if not response['tasks']:
            print_status("Task not found", "WARNING")
            return None
        
        task = response['tasks'][0]
        container = task['containers'][0] if task['containers'] else None
        
        if not container:
            print_status("No container found in task", "WARNING")
            return None
        
        # Get log stream name
        log_group = "/ecs/training-job"
        log_stream_prefix = f"ecs/training/{task_id}"
        
        # Get log streams
        streams_response = logs_client.describe_log_streams(
            logGroupName=log_group,
            logStreamNamePrefix=log_stream_prefix,
            orderBy='LastEventTime',
            descending=True,
            limit=1
        )
        
        if not streams_response['logStreams']:
            print_status("No log streams found", "WARNING")
            return None
        
        log_stream = streams_response['logStreams'][0]['logStreamName']
        
        # Get log events
        events_response = logs_client.get_log_events(
            logGroupName=log_group,
            logStreamName=log_stream,
            limit=100
        )
        
        logs = [event['message'] for event in events_response['events']]
        return logs
        
    except Exception as e:
        print_status(f"Error fetching logs: {e}", "ERROR")
        return None

def test_end_to_end():
    """Run complete end-to-end test"""
    print("\n" + "="*60)
    print("🚀 ML Platform End-to-End Test")
    print("="*60)
    
    total_steps = 6
    job_name = f"e2e-test-{int(time.time())}"
    # Get account ID from environment or use placeholder
    account_id = os.getenv('AWS_ACCOUNT_ID', 'YOUR_ACCOUNT_ID')
    image = f"{account_id}.dkr.ecr.{AWS_REGION}.amazonaws.com/training:latest"
    
    try:
        # Step 1: Create test data
        print_step(1, total_steps, "Creating test data")
        data_path = create_test_data()
        
        # Step 2: Submit job
        print_step(2, total_steps, "Submitting training job")
        job_id = submit_job(
            job_name=job_name,
            image=image,
            data_path=data_path,
            task_type='regression',
            algorithm='linear',
            n_estimators=10
        )
        
        if not job_id:
            print_status("Failed to submit job", "ERROR")
            return False
        
        # Step 3: Wait for job completion
        print_step(3, total_steps, "Monitoring job execution")
        final_status = wait_for_job_completion(job_id, max_wait_time=600)
        
        if not final_status:
            print_status("Job status check failed", "ERROR")
            return False
        
        # Step 4: Verify job status in DynamoDB
        print_step(4, total_steps, "Verifying job status in DynamoDB")
        job_status = final_status.get('status')
        print_status(f"Final job status: {job_status}", 
                    "SUCCESS" if job_status == 'completed' else "ERROR")
        
        # Step 5: Check S3 for model artifacts
        print_step(5, total_steps, "Verifying model artifacts in S3")
        model_exists = check_s3_model(job_name)
        
        if not model_exists and job_status == 'completed':
            print_status("Model artifacts not found in S3", "WARNING")
        
        # Step 6: Get ECS task logs
        print_step(6, total_steps, "Checking ECS task logs")
        if 'task_arn' in final_status:
            logs = get_ecs_task_logs(final_status['task_arn'])
            if logs:
                print_status("Recent log entries:", "INFO")
                for log in logs[-10:]:  # Show last 10 lines
                    print(f"  {log}")
        
        # Summary
        print("\n" + "="*60)
        print("📊 Test Summary")
        print("="*60)
        print(f"Job ID: {job_id}")
        print(f"Job Name: {job_name}")
        print(f"Final Status: {job_status}")
        print(f"Model in S3: {'Yes' if model_exists else 'No'}")
        
        success = job_status == 'completed' and model_exists
        if success:
            print_status("✅ End-to-end test PASSED!", "SUCCESS")
        else:
            print_status("❌ End-to-end test FAILED", "ERROR")
        
        return success
        
    except Exception as e:
        print_status(f"Test failed with exception: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_end_to_end()
    exit(0 if success else 1)

