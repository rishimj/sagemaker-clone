import pytest
import json
import os
from unittest.mock import patch

os.environ['DYNAMODB_TABLE'] = 'test-jobs'
os.environ['ECS_CLUSTER'] = 'test-cluster'
os.environ['SUBNET_ID'] = 'subnet-test'
os.environ['S3_BUCKET_NAME'] = 'test-bucket'

from lambda_functions.submit_job.handler import lambda_handler as submit_handler
from lambda_functions.get_job_status.handler import lambda_handler as status_handler

def test_full_job_workflow(dynamodb_resource, s3_client):
    """Test complete job submission and status check workflow"""
    # Setup
    table = dynamodb_resource.create_table(
        TableName='test-jobs',
        KeySchema=[{'AttributeName': 'job_id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'job_id', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST'
    )

    s3_client.create_bucket(Bucket='test-bucket')

    # Submit job
    submit_event = {
        'body': json.dumps({
            'job_name': 'integration-test',
            'image': 'training:latest',
            'input_data': 's3://test-bucket/data',
            'hyperparameters': {'epochs': 5}
        })
    }

    with patch('lambda_functions.submit_job.handler.start_ecs_task') as mock_ecs:
        mock_ecs.return_value = 'arn:aws:ecs:task/abc123'
        submit_response = submit_handler(submit_event, None)

    # Verify submission
    assert submit_response['statusCode'] == 200
    job_id = json.loads(submit_response['body'])['job_id']
    assert job_id.startswith('job-')

    # Get job status
    status_event = {
        'pathParameters': {'job_id': job_id}
    }

    status_response = status_handler(status_event, None)

    # Verify status
    assert status_response['statusCode'] == 200
    job = json.loads(status_response['body'])
    assert job['job_id'] == job_id
    assert job['status'] == 'running'
    assert job['job_name'] == 'integration-test'
    assert job['hyperparameters']['epochs'] == '5'
    assert 'task_arn' in job

def test_submit_and_query_multiple_jobs(dynamodb_resource):
    """Test submitting and querying multiple jobs"""
    table = dynamodb_resource.create_table(
        TableName='test-jobs',
        KeySchema=[{'AttributeName': 'job_id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'job_id', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST'
    )

    job_ids = []

    # Submit 3 jobs
    for i in range(3):
        event = {
            'body': json.dumps({
                'job_name': f'job-{i}',
                'image': 'training:latest',
                'input_data': 's3://bucket/data'
            })
        }

        with patch('lambda_functions.submit_job.handler.start_ecs_task') as mock:
            mock.return_value = f'task-arn-{i}'
            response = submit_handler(event, None)

        assert response['statusCode'] == 200
        job_id = json.loads(response['body'])['job_id']
        job_ids.append(job_id)

    # Query each job
    for i, job_id in enumerate(job_ids):
        event = {'pathParameters': {'job_id': job_id}}
        response = status_handler(event, None)

        assert response['statusCode'] == 200
        job = json.loads(response['body'])
        assert job['job_name'] == f'job-{i}'

def test_invalid_job_submission_then_valid(dynamodb_resource):
    """Test that invalid submission doesn't affect subsequent valid ones"""
    table = dynamodb_resource.create_table(
        TableName='test-jobs',
        KeySchema=[{'AttributeName': 'job_id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'job_id', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST'
    )

    # Try invalid submission
    invalid_event = {
        'body': json.dumps({'job_name': 'incomplete'})  # Missing required fields
    }

    invalid_response = submit_handler(invalid_event, None)
    assert invalid_response['statusCode'] == 400

    # Now submit valid job
    valid_event = {
        'body': json.dumps({
            'job_name': 'valid-job',
            'image': 'training:latest',
            'input_data': 's3://bucket/data'
        })
    }

    with patch('lambda_functions.submit_job.handler.start_ecs_task') as mock:
        mock.return_value = 'task-arn'
        valid_response = submit_handler(valid_event, None)

    assert valid_response['statusCode'] == 200
    job_id = json.loads(valid_response['body'])['job_id']

    # Verify it exists
    status_event = {'pathParameters': {'job_id': job_id}}
    status_response = status_handler(status_event, None)
    assert status_response['statusCode'] == 200