"""
Tests for ECS task configuration and role validation.

These tests verify that ECS tasks can be properly configured with the correct roles.
"""

import pytest
import boto3
import json
import os
from moto import mock_iam, mock_ecs
from dotenv import load_dotenv

load_dotenv()

# Test configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
AWS_ACCOUNT_ID = os.getenv('AWS_ACCOUNT_ID')

# Use real AWS if credentials are available
USE_REAL_AWS = os.getenv('AWS_ACCESS_KEY_ID') and AWS_ACCOUNT_ID

ECS_EXECUTION_ROLE_NAME = 'MLPlatformECSTaskExecutionRole'
ECS_TASK_ROLE_NAME = 'MLPlatformECSTaskRole'
TASK_DEFINITION_FAMILY = 'training-job'


@pytest.fixture
def iam_and_ecs_clients():
    """Create both IAM and ECS clients together."""
    if USE_REAL_AWS:
        return {
            'iam': boto3.client('iam', region_name=AWS_REGION),
            'ecs': boto3.client('ecs', region_name=AWS_REGION)
        }
    else:
        # Use both mocks together
        os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
        os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
        os.environ['AWS_DEFAULT_REGION'] = AWS_REGION
        with mock_iam(), mock_ecs():
            yield {
                'iam': boto3.client('iam', region_name=AWS_REGION),
                'ecs': boto3.client('ecs', region_name=AWS_REGION)
            }


def get_role_arn(role_name):
    """Get role ARN from role name."""
    if AWS_ACCOUNT_ID:
        return f"arn:aws:iam::{AWS_ACCOUNT_ID}:role/{role_name}"
    return f"arn:aws:iam::123456789012:role/{role_name}"


class TestECSTaskConfiguration:
    """Test ECS task configuration with roles."""
    
    def test_task_definition_has_required_roles(self, iam_and_ecs_clients):
        """Test that task definition has both execution and task roles configured."""
        iam_client = iam_and_ecs_clients['iam']
        ecs_client = iam_and_ecs_clients['ecs']
        
        if USE_REAL_AWS:
            response = ecs_client.describe_task_definition(taskDefinition=TASK_DEFINITION_FAMILY)
        else:
            # Set up roles and task definition in mock
            execution_role_arn = get_role_arn(ECS_EXECUTION_ROLE_NAME)
            task_role_arn = get_role_arn(ECS_TASK_ROLE_NAME)
            
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }
            iam_client.create_role(
                RoleName=ECS_EXECUTION_ROLE_NAME,
                AssumeRolePolicyDocument=json.dumps(trust_policy)
            )
            iam_client.create_role(
                RoleName=ECS_TASK_ROLE_NAME,
                AssumeRolePolicyDocument=json.dumps(trust_policy)
            )
            
            ecs_client.register_task_definition(
                family=TASK_DEFINITION_FAMILY,
                networkMode='awsvpc',
                requiresCompatibilities=['FARGATE'],
                cpu='256',
                memory='512',
                executionRoleArn=execution_role_arn,
                taskRoleArn=task_role_arn,
                containerDefinitions=[{
                    'name': 'training',
                    'image': 'training:latest',
                    'essential': True
                }]
            )
            response = ecs_client.describe_task_definition(taskDefinition=TASK_DEFINITION_FAMILY)
        
        task_def = response['taskDefinition']
        
        # Verify execution role is set
        assert 'executionRoleArn' in task_def, "Task definition must have executionRoleArn"
        assert task_def['executionRoleArn'] is not None, "executionRoleArn must not be None"
        assert ECS_EXECUTION_ROLE_NAME in task_def['executionRoleArn'], \
            f"Task definition should use {ECS_EXECUTION_ROLE_NAME}"
        
        # Verify task role is set
        assert 'taskRoleArn' in task_def, "Task definition must have taskRoleArn"
        assert task_def['taskRoleArn'] is not None, "taskRoleArn must not be None"
        assert ECS_TASK_ROLE_NAME in task_def['taskRoleArn'], \
            f"Task definition should use {ECS_TASK_ROLE_NAME}"
        
        # Verify roles are different (they serve different purposes)
        assert task_def['executionRoleArn'] != task_def['taskRoleArn'], \
            "Execution role and task role should be different"
    
    def test_task_definition_roles_exist(self, iam_and_ecs_clients):
        """Test that the roles referenced in task definition actually exist."""
        iam_client = iam_and_ecs_clients['iam']
        ecs_client = iam_and_ecs_clients['ecs']
        
        if USE_REAL_AWS:
            # Get task definition
            task_response = ecs_client.describe_task_definition(taskDefinition=TASK_DEFINITION_FAMILY)
            task_def = task_response['taskDefinition']
            
            execution_role_arn = task_def['executionRoleArn']
            task_role_arn = task_def['taskRoleArn']
            
            # Extract role names from ARNs
            execution_role_name = execution_role_arn.split('/')[-1]
            task_role_name = task_role_arn.split('/')[-1]
            
            # Verify roles exist
            try:
                iam_client.get_role(RoleName=execution_role_name)
                iam_client.get_role(RoleName=task_role_name)
            except iam_client.exceptions.NoSuchEntityException as e:
                pytest.fail(f"Role referenced in task definition does not exist: {e}")
        else:
            # In mock, create roles and verify
            execution_role_arn = get_role_arn(ECS_EXECUTION_ROLE_NAME)
            task_role_arn = get_role_arn(ECS_TASK_ROLE_NAME)
            
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }
            iam_client.create_role(
                RoleName=ECS_EXECUTION_ROLE_NAME,
                AssumeRolePolicyDocument=json.dumps(trust_policy)
            )
            iam_client.create_role(
                RoleName=ECS_TASK_ROLE_NAME,
                AssumeRolePolicyDocument=json.dumps(trust_policy)
            )
            
            ecs_client.register_task_definition(
                family=TASK_DEFINITION_FAMILY,
                networkMode='awsvpc',
                requiresCompatibilities=['FARGATE'],
                cpu='256',
                memory='512',
                executionRoleArn=execution_role_arn,
                taskRoleArn=task_role_arn,
                containerDefinitions=[{
                    'name': 'training',
                    'image': 'training:latest',
                    'essential': True
                }]
            )
            
            # Verify roles exist
            iam_client.get_role(RoleName=ECS_EXECUTION_ROLE_NAME)
            iam_client.get_role(RoleName=ECS_TASK_ROLE_NAME)
    
    def test_task_definition_fargate_configuration(self, iam_and_ecs_clients):
        """Test that task definition is properly configured for Fargate."""
        iam_client = iam_and_ecs_clients['iam']
        ecs_client = iam_and_ecs_clients['ecs']
        
        if USE_REAL_AWS:
            response = ecs_client.describe_task_definition(taskDefinition=TASK_DEFINITION_FAMILY)
        else:
            execution_role_arn = get_role_arn(ECS_EXECUTION_ROLE_NAME)
            task_role_arn = get_role_arn(ECS_TASK_ROLE_NAME)
            
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }
            iam_client.create_role(
                RoleName=ECS_EXECUTION_ROLE_NAME,
                AssumeRolePolicyDocument=json.dumps(trust_policy)
            )
            iam_client.create_role(
                RoleName=ECS_TASK_ROLE_NAME,
                AssumeRolePolicyDocument=json.dumps(trust_policy)
            )
            
            ecs_client.register_task_definition(
                family=TASK_DEFINITION_FAMILY,
                networkMode='awsvpc',
                requiresCompatibilities=['FARGATE'],
                cpu='256',
                memory='512',
                executionRoleArn=execution_role_arn,
                taskRoleArn=task_role_arn,
                containerDefinitions=[{
                    'name': 'training',
                    'image': 'training:latest',
                    'essential': True
                }]
            )
            response = ecs_client.describe_task_definition(taskDefinition=TASK_DEFINITION_FAMILY)
        
        task_def = response['taskDefinition']
        
        # Verify Fargate configuration
        assert 'FARGATE' in task_def['requiresCompatibilities'], \
            "Task definition must support FARGATE"
        assert task_def['networkMode'] == 'awsvpc', \
            "Fargate tasks must use awsvpc network mode"
        assert 'cpu' in task_def, "Task definition must specify CPU"
        assert 'memory' in task_def, "Task definition must specify memory"

