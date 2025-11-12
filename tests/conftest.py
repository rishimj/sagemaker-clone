import pytest
import boto3
from moto import mock_s3, mock_dynamodb, mock_ecs
import os
from dotenv import load_dotenv

load_dotenv()

@pytest.fixture
def aws_credentials():
    """Mock AWS Credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

@pytest.fixture
def s3_client(aws_credentials):
    """Create mock S3 client"""
    with mock_s3():
        yield boto3.client('s3', region_name='us-east-1')

@pytest.fixture
def dynamodb_resource(aws_credentials):
    """Create mock DynamoDB resource"""
    with mock_dynamodb():
        yield boto3.resource('dynamodb', region_name='us-east-1')

@pytest.fixture
def ecs_client(aws_credentials):
    """Create mock ECS client"""
    with mock_ecs():
        yield boto3.client('ecs', region_name='us-east-1')