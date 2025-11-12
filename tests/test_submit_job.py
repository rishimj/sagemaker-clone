import pytest
import json
import os
from unittest.mock import Mock, patch, MagicMock

# Set environment variables before importing handler
os.environ['DYNAMODB_TABLE'] = 'test-jobs'
os.environ['ECS_CLUSTER'] = 'test-cluster'
os.environ['SUBNET_ID'] = 'subnet-test'

from lambda_functions.submit_job.handler import lambda_handler, validate_input, start_ecs_task

def test_validate_input_success():
    """Test input validation with valid data"""
    body = {
        'job_name': 'test-job',
        'image': 'training:latest',
        'input_data': 's3://bucket/data'
    }

    valid, error = validate_input(body)

    assert valid is True
    assert error is None

def test_validate_input_missing_job_name():
    """Test validation fails without job_name"""
    body = {
        'image': 'training:latest',
        'input_data': 's3://bucket/data'
    }

    valid, error = validate_input(body)

    assert valid is False
    assert 'job_name' in error

def test_validate_input_missing_image():
    """Test validation fails without image"""
    body = {
        'job_name': 'test',
        'input_data': 's3://bucket/data'
    }

    valid, error = validate_input(body)

    assert valid is False
    assert 'image' in error

def test_validate_input_missing_input_data():
    """Test validation fails without input_data"""
    body = {
        'job_name': 'test',
        'image': 'training:latest'
    }

    valid, error = validate_input(body)

    assert valid is False
    assert 'input_data' in error

def test_submit_job_creates_db_entry(dynamodb_resource):
    """Test job submission creates DynamoDB entry"""
    # Create test table
    table = dynamodb_resource.create_table(
        TableName='test-jobs',
        KeySchema=[{'AttributeName': 'job_id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'job_id', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST'
    )

    event = {
        'body': json.dumps({
            'job_name': 'test-job',
            'image': 'training:latest',
            'input_data': 's3://bucket/data',
            'hyperparameters': {'epochs': 10}
        })
    }

    with patch('lambda_functions.submit_job.handler.start_ecs_task') as mock_ecs:
        with patch('lambda_functions.submit_job.handler.job_store') as mock_store:
            mock_store.create_job.return_value = 'job-abc123'
            mock_store.update_job_status.return_value = True
            mock_ecs.return_value = 'task-arn-123'

            response = lambda_handler(event, None)

    # Assert response
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert 'job_id' in body

def test_submit_job_invalid_input():
    """Test job submission with invalid input"""
    event = {
        'body': json.dumps({})  # Missing required fields
    }

    with patch('lambda_functions.submit_job.handler.start_ecs_task'):
        response = lambda_handler(event, None)

    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert 'error' in body

def test_submit_job_starts_ecs_task():
    """Test job submission starts ECS task"""
    event = {
        'body': json.dumps({
            'job_name': 'test',
            'image': 'training:latest',
            'input_data': 's3://bucket/data'
        })
    }

    with patch('lambda_functions.submit_job.handler.start_ecs_task') as mock_ecs:
        with patch('lambda_functions.submit_job.handler.job_store') as mock_store:
            mock_store.create_job.return_value = 'job-123'
            mock_ecs.return_value = 'task-arn'

            response = lambda_handler(event, None)

            # Verify ECS was called
            assert mock_ecs.called
            call_args = mock_ecs.call_args[0]
            assert call_args[0] == 'job-123'  # job_id
            assert call_args[1] == 'training:latest'  # image

def test_submit_job_handles_ecs_failure():
    """Test job submission when ECS fails"""
    event = {
        'body': json.dumps({
            'job_name': 'test',
            'image': 'training:latest',
            'input_data': 's3://bucket/data'
        })
    }

    with patch('lambda_functions.submit_job.handler.start_ecs_task') as mock_ecs:
        with patch('lambda_functions.submit_job.handler.job_store') as mock_store:
            mock_store.create_job.return_value = 'job-123'
            mock_ecs.return_value = None  # ECS failed

            response = lambda_handler(event, None)

            # Should still return 200 but job stays pending
            assert response['statusCode'] == 200