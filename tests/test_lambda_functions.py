#!/usr/bin/env python3
"""
Test script for Lambda functions
Tests submit-job and get-job-status Lambda functions
"""

import boto3
import json
import time
import sys
import argparse
import os

def test_submit_job(job_name=None, image=None, input_data=None, hyperparameters=None):
    """Test submit-job Lambda function"""
    lambda_client = boto3.client('lambda', region_name='us-east-1')
    
    # Get from environment
    aws_account_id = os.getenv('AWS_ACCOUNT_ID', 'YOUR_ACCOUNT_ID')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    s3_bucket = os.getenv('S3_BUCKET_NAME', 'your-ml-platform-bucket')
    
    # Default values
    if not job_name:
        job_name = f"test-job-{int(time.time())}"
    if not image:
        image = f"{aws_account_id}.dkr.ecr.{aws_region}.amazonaws.com/training:latest"
    if not input_data:
        input_data = f"s3://{s3_bucket}/data/test.csv"
    if not hyperparameters:
        hyperparameters = {
            "epochs": 10,
            "learning_rate": 0.001
        }
    
    payload = {
        "body": json.dumps({
            "job_name": job_name,
            "image": image,
            "input_data": input_data,
            "hyperparameters": hyperparameters
        })
    }
    
    print("=" * 60)
    print("Testing submit-job Lambda function")
    print("=" * 60)
    print(f"Job name: {job_name}")
    print(f"Image: {image}")
    print(f"Input data: {input_data}")
    print(f"Hyperparameters: {hyperparameters}")
    print("\nInvoking Lambda...")
    
    try:
        response = lambda_client.invoke(
            FunctionName='submit-job',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        response_payload = json.loads(response['Payload'].read())
        
        if response_payload.get('statusCode') == 200:
            body = json.loads(response_payload.get('body', '{}'))
            job_id = body.get('job_id')
            print(f"✓ Job created successfully!")
            print(f"  Job ID: {job_id}")
            print(f"  Status Code: {response['StatusCode']}")
            return job_id
        else:
            print(f"✗ Error: Status code {response_payload.get('statusCode')}")
            print(f"  Body: {response_payload.get('body')}")
            return None
            
    except Exception as e:
        print(f"✗ Error invoking Lambda: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_get_job_status(job_id):
    """Test get-job-status Lambda function"""
    lambda_client = boto3.client('lambda', region_name='us-east-1')
    
    payload = {
        "pathParameters": {
            "job_id": job_id
        }
    }
    
    print("\n" + "=" * 60)
    print("Testing get-job-status Lambda function")
    print("=" * 60)
    print(f"Job ID: {job_id}")
    print("\nInvoking Lambda...")
    
    try:
        response = lambda_client.invoke(
            FunctionName='get-job-status',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        response_payload = json.loads(response['Payload'].read())
        
        if response_payload.get('statusCode') == 200:
            body = json.loads(response_payload.get('body', '{}'))
            print("✓ Job status retrieved successfully!")
            print("\nJob Details:")
            print(f"  Job ID: {body.get('job_id')}")
            print(f"  Job Name: {body.get('job_name')}")
            print(f"  Status: {body.get('status')}")
            print(f"  Image: {body.get('image')}")
            print(f"  S3 Input: {body.get('s3_input')}")
            print(f"  S3 Output: {body.get('s3_output')}")
            print(f"  Task ARN: {body.get('task_arn', 'N/A')}")
            print(f"  Created: {body.get('created_at')}")
            return body
        elif response_payload.get('statusCode') == 404:
            print(f"✗ Job not found: {job_id}")
            return None
        else:
            print(f"✗ Error: Status code {response_payload.get('statusCode')}")
            print(f"  Body: {response_payload.get('body')}")
            return None
            
    except Exception as e:
        print(f"✗ Error invoking Lambda: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    parser = argparse.ArgumentParser(description='Test Lambda functions')
    parser.add_argument('--job-id', help='Job ID to check status (if not provided, will submit a new job)')
    parser.add_argument('--job-name', help='Job name for new job')
    parser.add_argument('--image', help='Docker image URI')
    parser.add_argument('--input-data', help='S3 input data path')
    parser.add_argument('--epochs', type=int, help='Number of epochs')
    parser.add_argument('--learning-rate', type=float, help='Learning rate')
    
    args = parser.parse_args()
    
    if args.job_id:
        # Just check status
        test_get_job_status(args.job_id)
    else:
        # Submit new job and check status
        hyperparameters = {}
        if args.epochs:
            hyperparameters['epochs'] = args.epochs
        if args.learning_rate:
            hyperparameters['learning_rate'] = args.learning_rate
        if not hyperparameters:
            hyperparameters = None
        
        job_id = test_submit_job(
            job_name=args.job_name,
            image=args.image,
            input_data=args.input_data,
            hyperparameters=hyperparameters
        )
        
        if job_id:
            print("\nWaiting 2 seconds before checking status...")
            time.sleep(2)
            test_get_job_status(job_id)
            
            print("\n" + "=" * 60)
            print("Test Complete!")
            print("=" * 60)
            print(f"\nTo check status again, run:")
            print(f"  python3 test_lambda_functions.py --job-id {job_id}")
            print(f"\nTo check ECS task status:")
            print(f"  aws ecs describe-tasks --cluster training-cluster --tasks <task-arn>")
            print(f"\nTo check CloudWatch logs:")
            print(f"  aws logs tail /ecs/training-job --follow")

if __name__ == '__main__':
    main()

