import pytest
import json
import os

os.environ['DYNAMODB_TABLE'] = 'test-jobs'

from lambda_functions.get_job_status.handler import lambda_handler

def test_get_job_status_success(dynamodb_resource):
    """Test retrieving existing job"""
    # Create table and job
    table = dynamodb_resource.create_table(
        TableName='test-jobs',
        KeySchema=[{'AttributeName': 'job_id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'job_id', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST'
    )

    table.put_item(Item={
        'job_id': 'job-123',
        'status': 'completed',
        'job_name': 'test-job',
        'created_at': 1699300000
    })

    event = {
        'pathParameters': {'job_id': 'job-123'}
    }

    response = lambda_handler(event, None)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['job_id'] == 'job-123'
    assert body['status'] == 'completed'
    assert body['job_name'] == 'test-job'

def test_get_job_status_not_found(dynamodb_resource):
    """Test retrieving non-existent job"""
    table = dynamodb_resource.create_table(
        TableName='test-jobs',
        KeySchema=[{'AttributeName': 'job_id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'job_id', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST'
    )

    event = {
        'pathParameters': {'job_id': 'non-existent'}
    }

    response = lambda_handler(event, None)

    assert response['statusCode'] == 404
    body = json.loads(response['body'])
    assert 'error' in body

def test_get_job_status_missing_parameter():
    """Test with missing job_id parameter"""
    event = {
        'pathParameters': {}
    }

    response = lambda_handler(event, None)

    assert response['statusCode'] == 400

def test_get_job_status_returns_all_fields(dynamodb_resource):
    """Test that all job fields are returned"""
    table = dynamodb_resource.create_table(
        TableName='test-jobs',
        KeySchema=[{'AttributeName': 'job_id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'job_id', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST'
    )

    table.put_item(Item={
        'job_id': 'job-456',
        'status': 'running',
        'job_name': 'full-test',
        'image': 'training:v1',
        's3_input': 's3://bucket/input',
        's3_output': 's3://bucket/output',
        'task_arn': 'arn:aws:ecs:task/123',
        'hyperparameters': {'epochs': 10},
        'created_at': 1699300000
    })

    event = {
        'pathParameters': {'job_id': 'job-456'}
    }

    response = lambda_handler(event, None)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['status'] == 'running'
    assert body['image'] == 'training:v1'
    assert body['task_arn'] == 'arn:aws:ecs:task/123'
    assert body['hyperparameters']['epochs'] == '10'