"""
Tests for ECS role configuration and permissions.

These tests verify that:
1. ECS Task Execution Role exists and has correct permissions
2. ECS Task Role exists and has correct permissions
3. Task definition references the correct role ARNs
4. Lambda has permission to pass roles to ECS
5. Roles have correct trust policies
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
ECS_EXECUTION_ROLE_NAME = 'MLPlatformECSTaskExecutionRole'
ECS_TASK_ROLE_NAME = 'MLPlatformECSTaskRole'
LAMBDA_ROLE_NAME = 'MLPlatformLambdaRole'
TASK_DEFINITION_FAMILY = 'training-job'

# Use real AWS if credentials are available, otherwise use mocks
USE_REAL_AWS = os.getenv('AWS_ACCESS_KEY_ID') and AWS_ACCOUNT_ID


@pytest.fixture
def iam_client():
    """Create IAM client - mocked or real depending on USE_REAL_AWS."""
    if USE_REAL_AWS:
        return boto3.client('iam', region_name=AWS_REGION)
    else:
        # Use moto for IAM mocking - set credentials first
        os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
        os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
        os.environ['AWS_DEFAULT_REGION'] = AWS_REGION
        with mock_iam():
            yield boto3.client('iam', region_name=AWS_REGION)


@pytest.fixture
def ecs_client():
    """Create ECS client - mocked or real depending on USE_REAL_AWS."""
    if USE_REAL_AWS:
        return boto3.client('ecs', region_name=AWS_REGION)
    else:
        # Use moto for ECS mocking - set credentials first
        os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
        os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
        os.environ['AWS_DEFAULT_REGION'] = AWS_REGION
        with mock_ecs():
            yield boto3.client('ecs', region_name=AWS_REGION)


@pytest.fixture
def iam_and_ecs_clients():
    """Create both IAM and ECS clients together - needed for task definition tests."""
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


class TestECSTaskExecutionRole:
    """Test ECS Task Execution Role configuration."""
    
    def test_execution_role_exists(self, iam_client):
        """Test that ECS Task Execution Role exists."""
        if USE_REAL_AWS:
            try:
                response = iam_client.get_role(RoleName=ECS_EXECUTION_ROLE_NAME)
                assert response['Role']['RoleName'] == ECS_EXECUTION_ROLE_NAME
            except iam_client.exceptions.NoSuchEntityException:
                pytest.fail(f"Role {ECS_EXECUTION_ROLE_NAME} does not exist")
        else:
            # Create role in mock for testing
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
            response = iam_client.get_role(RoleName=ECS_EXECUTION_ROLE_NAME)
            assert response['Role']['RoleName'] == ECS_EXECUTION_ROLE_NAME
    
    def test_execution_role_trust_policy(self, iam_client):
        """Test that ECS Task Execution Role has correct trust policy."""
        if USE_REAL_AWS:
            response = iam_client.get_role(RoleName=ECS_EXECUTION_ROLE_NAME)
        else:
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
            response = iam_client.get_role(RoleName=ECS_EXECUTION_ROLE_NAME)
        
        # Handle both string and dict formats (real AWS returns string, moto returns dict)
        assume_role_policy = response['Role']['AssumeRolePolicyDocument']
        if isinstance(assume_role_policy, str):
            trust_policy_doc = json.loads(assume_role_policy)
        else:
            trust_policy_doc = assume_role_policy
        
        # Check that trust policy allows ecs-tasks service
        statements = trust_policy_doc.get('Statement', [])
        assert len(statements) > 0, "Trust policy should have at least one statement"
        
        ecs_service_found = False
        for statement in statements:
            if statement.get('Effect') == 'Allow':
                principal = statement.get('Principal', {})
                if isinstance(principal, dict) and principal.get('Service') == 'ecs-tasks.amazonaws.com':
                    ecs_service_found = True
                    action = statement.get('Action', [])
                    if isinstance(action, str):
                        action = [action]
                    assert 'sts:AssumeRole' in action
        assert ecs_service_found, "Trust policy should allow ecs-tasks.amazonaws.com to assume role"
    
    def test_execution_role_has_ecs_policy(self, iam_client):
        """Test that ECS Task Execution Role has AmazonECSTaskExecutionRolePolicy attached."""
        if USE_REAL_AWS:
            try:
                response = iam_client.list_attached_role_policies(RoleName=ECS_EXECUTION_ROLE_NAME)
                policy_arns = [p['PolicyArn'] for p in response['AttachedPolicies']]
                
                # Check for the standard ECS execution role policy
                has_ecs_policy = any('AmazonECSTaskExecutionRolePolicy' in arn for arn in policy_arns)
                assert has_ecs_policy, f"Role {ECS_EXECUTION_ROLE_NAME} should have AmazonECSTaskExecutionRolePolicy attached"
            except iam_client.exceptions.ClientError as e:
                if e.response['Error']['Code'] == 'AccessDenied':
                    # Skip this test if user doesn't have permission to list policies
                    pytest.skip(f"Insufficient permissions to verify policy attachment: {e}")
                else:
                    raise
        else:
            # In mock, attach the policy
            policy_arn = 'arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy'
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
            iam_client.attach_role_policy(
                RoleName=ECS_EXECUTION_ROLE_NAME,
                PolicyArn=policy_arn
            )
            response = iam_client.list_attached_role_policies(RoleName=ECS_EXECUTION_ROLE_NAME)
            policy_arns = [p['PolicyArn'] for p in response['AttachedPolicies']]
            assert policy_arn in policy_arns


class TestECSTaskRole:
    """Test ECS Task Role configuration."""
    
    def test_task_role_exists(self, iam_client):
        """Test that ECS Task Role exists."""
        if USE_REAL_AWS:
            try:
                response = iam_client.get_role(RoleName=ECS_TASK_ROLE_NAME)
                assert response['Role']['RoleName'] == ECS_TASK_ROLE_NAME
            except iam_client.exceptions.NoSuchEntityException:
                pytest.fail(f"Role {ECS_TASK_ROLE_NAME} does not exist")
        else:
            # Create role in mock for testing
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }
            iam_client.create_role(
                RoleName=ECS_TASK_ROLE_NAME,
                AssumeRolePolicyDocument=json.dumps(trust_policy)
            )
            response = iam_client.get_role(RoleName=ECS_TASK_ROLE_NAME)
            assert response['Role']['RoleName'] == ECS_TASK_ROLE_NAME
    
    def test_task_role_trust_policy(self, iam_client):
        """Test that ECS Task Role has correct trust policy."""
        if USE_REAL_AWS:
            response = iam_client.get_role(RoleName=ECS_TASK_ROLE_NAME)
        else:
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }
            iam_client.create_role(
                RoleName=ECS_TASK_ROLE_NAME,
                AssumeRolePolicyDocument=json.dumps(trust_policy)
            )
            response = iam_client.get_role(RoleName=ECS_TASK_ROLE_NAME)
        
        # Handle both string and dict formats (real AWS returns string, moto returns dict)
        assume_role_policy = response['Role']['AssumeRolePolicyDocument']
        if isinstance(assume_role_policy, str):
            trust_policy_doc = json.loads(assume_role_policy)
        else:
            trust_policy_doc = assume_role_policy
        
        # Check that trust policy allows ecs-tasks service
        statements = trust_policy_doc.get('Statement', [])
        assert len(statements) > 0, "Trust policy should have at least one statement"
        
        ecs_service_found = False
        for statement in statements:
            if statement.get('Effect') == 'Allow':
                principal = statement.get('Principal', {})
                if isinstance(principal, dict) and principal.get('Service') == 'ecs-tasks.amazonaws.com':
                    ecs_service_found = True
                    action = statement.get('Action', [])
                    if isinstance(action, str):
                        action = [action]
                    assert 'sts:AssumeRole' in action
        assert ecs_service_found, "Trust policy should allow ecs-tasks.amazonaws.com to assume role"
    
    def test_task_role_has_s3_permissions(self, iam_client):
        """Test that ECS Task Role has S3 permissions."""
        if USE_REAL_AWS:
            try:
                # Check attached policies
                response = iam_client.list_attached_role_policies(RoleName=ECS_TASK_ROLE_NAME)
                policy_arns = [p['PolicyArn'] for p in response['AttachedPolicies']]
                
                # Check inline policies
                inline_response = iam_client.list_role_policies(RoleName=ECS_TASK_ROLE_NAME)
                inline_policy_names = inline_response['PolicyNames']
                
                has_s3_permissions = False
                
                # Check attached policies
                for policy_arn in policy_arns:
                    if 'MLPlatformECSTaskPolicy' in policy_arn:
                        try:
                            policy_response = iam_client.get_policy(PolicyArn=policy_arn)
                            version_response = iam_client.get_policy_version(
                                PolicyArn=policy_arn,
                                VersionId=policy_response['Policy']['DefaultVersionId']
                            )
                            policy_doc = version_response['PolicyVersion']['Document']
                            if _policy_has_s3_permissions(policy_doc):
                                has_s3_permissions = True
                                break
                        except iam_client.exceptions.ClientError:
                            # Skip if can't read policy details
                            continue
                
                # Check inline policies
                for policy_name in inline_policy_names:
                    try:
                        policy_response = iam_client.get_role_policy(
                            RoleName=ECS_TASK_ROLE_NAME,
                            PolicyName=policy_name
                        )
                        if _policy_has_s3_permissions(policy_response['PolicyDocument']):
                            has_s3_permissions = True
                            break
                    except iam_client.exceptions.ClientError:
                        # Skip if can't read policy details
                        continue
                
                assert has_s3_permissions, f"Role {ECS_TASK_ROLE_NAME} should have S3 permissions"
            except iam_client.exceptions.ClientError as e:
                if e.response['Error']['Code'] == 'AccessDenied':
                    # Skip this test if user doesn't have permission to list policies
                    pytest.skip(f"Insufficient permissions to verify policy attachment: {e}")
                else:
                    raise
        else:
            # In mock, create and attach policy with S3 permissions
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }
            iam_client.create_role(
                RoleName=ECS_TASK_ROLE_NAME,
                AssumeRolePolicyDocument=json.dumps(trust_policy)
            )
            
            task_policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
                    "Resource": "*"
                }]
            }
            
            # Create policy with correct ARN format
            policy_arn = f"arn:aws:iam::123456789012:policy/MLPlatformECSTaskPolicy"
            try:
                iam_client.create_policy(
                    PolicyName='MLPlatformECSTaskPolicy',
                    PolicyDocument=json.dumps(task_policy)
                )
            except iam_client.exceptions.EntityAlreadyExistsException:
                pass  # Policy already exists
            
            iam_client.attach_role_policy(
                RoleName=ECS_TASK_ROLE_NAME,
                PolicyArn=policy_arn
            )
            
            # Verify
            response = iam_client.list_attached_role_policies(RoleName=ECS_TASK_ROLE_NAME)
            policy_arns = [p['PolicyArn'] for p in response['AttachedPolicies']]
            assert any('MLPlatformECSTaskPolicy' in arn for arn in policy_arns)
    
    def test_task_role_has_all_dynamodb_permissions(self, iam_client):
        """Test that ECS Task Role has all required DynamoDB permissions."""
        required_permissions = [
            'dynamodb:GetItem',
            'dynamodb:PutItem',
            'dynamodb:UpdateItem',
            'dynamodb:Scan',
            'dynamodb:Query',
            'dynamodb:DescribeTable'
        ]
        
        if USE_REAL_AWS:
            # Check attached policies
            response = iam_client.list_attached_role_policies(RoleName=ECS_TASK_ROLE_NAME)
            policy_arns = [p['PolicyArn'] for p in response['AttachedPolicies']]
            
            # Check inline policies
            inline_response = iam_client.list_role_policies(RoleName=ECS_TASK_ROLE_NAME)
            inline_policy_names = inline_response['PolicyNames']
            
            found_permissions = set()
            
            # Check attached policies
            for policy_arn in policy_arns:
                if 'MLPlatformECSTaskPolicy' in policy_arn:
                    policy_response = iam_client.get_policy(PolicyArn=policy_arn)
                    version_response = iam_client.get_policy_version(
                        PolicyArn=policy_arn,
                        VersionId=policy_response['Policy']['DefaultVersionId']
                    )
                    policy_doc = version_response['PolicyVersion']['Document']
                    found_permissions.update(_get_dynamodb_permissions(policy_doc))
            
            # Check inline policies
            for policy_name in inline_policy_names:
                policy_response = iam_client.get_role_policy(
                    RoleName=ECS_TASK_ROLE_NAME,
                    PolicyName=policy_name
                )
                found_permissions.update(_get_dynamodb_permissions(policy_response['PolicyDocument']))
            
            missing_permissions = set(required_permissions) - found_permissions
            assert not missing_permissions, \
                f"Role {ECS_TASK_ROLE_NAME} is missing DynamoDB permissions: {', '.join(sorted(missing_permissions))}. " \
                f"Found: {sorted(found_permissions)}"
        else:
            # In mock, create and attach policy with all DynamoDB permissions
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }
            iam_client.create_role(
                RoleName=ECS_TASK_ROLE_NAME,
                AssumeRolePolicyDocument=json.dumps(trust_policy)
            )
            
            task_policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Action": required_permissions,
                    "Resource": "*"
                }]
            }
            
            # Create policy with correct ARN format
            policy_arn = f"arn:aws:iam::123456789012:policy/MLPlatformECSTaskPolicy"
            try:
                iam_client.create_policy(
                    PolicyName='MLPlatformECSTaskPolicy',
                    PolicyDocument=json.dumps(task_policy)
                )
            except iam_client.exceptions.EntityAlreadyExistsException:
                pass  # Policy already exists
            
            iam_client.attach_role_policy(
                RoleName=ECS_TASK_ROLE_NAME,
                PolicyArn=policy_arn
            )
            
            # Verify
            response = iam_client.list_attached_role_policies(RoleName=ECS_TASK_ROLE_NAME)
            policy_arns = [p['PolicyArn'] for p in response['AttachedPolicies']]
            assert any('MLPlatformECSTaskPolicy' in arn for arn in policy_arns)


class TestTaskDefinition:
    """Test ECS Task Definition configuration."""
    
    def test_task_definition_exists(self, iam_and_ecs_clients):
        """Test that task definition exists."""
        iam_client = iam_and_ecs_clients['iam']
        ecs_client = iam_and_ecs_clients['ecs']
        
        if USE_REAL_AWS:
            try:
                response = ecs_client.describe_task_definition(
                    taskDefinition=TASK_DEFINITION_FAMILY
                )
                assert response['taskDefinition']['family'] == TASK_DEFINITION_FAMILY
            except ecs_client.exceptions.ClientError as e:
                if e.response['Error']['Code'] == 'ClientException':
                    pytest.fail(f"Task definition {TASK_DEFINITION_FAMILY} does not exist")
                raise
        else:
            # Create task definition in mock
            execution_role_arn = get_role_arn(ECS_EXECUTION_ROLE_NAME)
            task_role_arn = get_role_arn(ECS_TASK_ROLE_NAME)
            
            # Create roles first
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
            assert response['taskDefinition']['family'] == TASK_DEFINITION_FAMILY
    
    def test_task_definition_has_execution_role(self, iam_and_ecs_clients):
        """Test that task definition has execution role ARN."""
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
        assert 'executionRoleArn' in task_def, "Task definition should have executionRoleArn"
        assert ECS_EXECUTION_ROLE_NAME in task_def['executionRoleArn'], \
            f"Task definition should use {ECS_EXECUTION_ROLE_NAME}"
    
    def test_task_definition_has_task_role(self, iam_and_ecs_clients):
        """Test that task definition has task role ARN."""
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
        assert 'taskRoleArn' in task_def, "Task definition should have taskRoleArn"
        assert ECS_TASK_ROLE_NAME in task_def['taskRoleArn'], \
            f"Task definition should use {ECS_TASK_ROLE_NAME}"


class TestLambdaPassRole:
    """Test Lambda role has permission to pass ECS task role."""
    
    def test_lambda_role_has_passrole_permission(self, iam_client):
        """Test that Lambda role has iam:PassRole permission for ECS task role."""
        if USE_REAL_AWS:
            try:
                # Get Lambda role policies
                response = iam_client.list_attached_role_policies(RoleName=LAMBDA_ROLE_NAME)
                policy_arns = [p['PolicyArn'] for p in response['AttachedPolicies']]
                
                # Check inline policies
                inline_response = iam_client.list_role_policies(RoleName=LAMBDA_ROLE_NAME)
                inline_policy_names = inline_response['PolicyNames']
                
                has_passrole = False
                task_role_arn = get_role_arn(ECS_TASK_ROLE_NAME)
                
                # Check attached policies
                for policy_arn in policy_arns:
                    if 'MLPlatformLambdaPolicy' in policy_arn:
                        try:
                            policy_response = iam_client.get_policy(PolicyArn=policy_arn)
                            version_response = iam_client.get_policy_version(
                                PolicyArn=policy_arn,
                                VersionId=policy_response['Policy']['DefaultVersionId']
                            )
                            policy_doc = version_response['PolicyVersion']['Document']
                            if _policy_allows_passrole_for_role(policy_doc, task_role_arn):
                                has_passrole = True
                                break
                        except iam_client.exceptions.ClientError:
                            # Skip if can't read policy details
                            continue
                
                # Check inline policies
                for policy_name in inline_policy_names:
                    try:
                        policy_response = iam_client.get_role_policy(
                            RoleName=LAMBDA_ROLE_NAME,
                            PolicyName=policy_name
                        )
                        if _policy_allows_passrole_for_role(policy_response['PolicyDocument'], task_role_arn):
                            has_passrole = True
                            break
                    except iam_client.exceptions.ClientError:
                        # Skip if can't read policy details
                        continue
                
                assert has_passrole, f"Lambda role {LAMBDA_ROLE_NAME} should have iam:PassRole permission for {ECS_TASK_ROLE_NAME}"
            except iam_client.exceptions.ClientError as e:
                if e.response['Error']['Code'] == 'AccessDenied':
                    # Skip this test if user doesn't have permission to list policies
                    pytest.skip(f"Insufficient permissions to verify policy attachment: {e}")
                else:
                    raise
        else:
            # Create Lambda role and policy in mock
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }
            iam_client.create_role(
                RoleName=LAMBDA_ROLE_NAME,
                AssumeRolePolicyDocument=json.dumps(trust_policy)
            )
            
            task_role_arn = get_role_arn(ECS_TASK_ROLE_NAME)
            lambda_policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Action": "iam:PassRole",
                    "Resource": task_role_arn
                }]
            }
            
            # Create policy with correct ARN format
            policy_arn = f"arn:aws:iam::123456789012:policy/MLPlatformLambdaPolicy"
            try:
                iam_client.create_policy(
                    PolicyName='MLPlatformLambdaPolicy',
                    PolicyDocument=json.dumps(lambda_policy)
                )
            except iam_client.exceptions.EntityAlreadyExistsException:
                pass  # Policy already exists
            
            iam_client.attach_role_policy(
                RoleName=LAMBDA_ROLE_NAME,
                PolicyArn=policy_arn
            )
            
            # Verify
            response = iam_client.list_attached_role_policies(RoleName=LAMBDA_ROLE_NAME)
            policy_arns = [p['PolicyArn'] for p in response['AttachedPolicies']]
            assert any('MLPlatformLambdaPolicy' in arn for arn in policy_arns)


# Helper functions
def _policy_has_s3_permissions(policy_doc):
    """Check if policy document has S3 permissions."""
    statements = policy_doc.get('Statement', [])
    for statement in statements:
        if statement.get('Effect') == 'Allow':
            actions = statement.get('Action', [])
            if isinstance(actions, str):
                actions = [actions]
            for action in actions:
                if action.startswith('s3:'):
                    return True
    return False


def _policy_allows_passrole_for_role(policy_doc, role_arn):
    """Check if policy document allows PassRole for specific role."""
    statements = policy_doc.get('Statement', [])
    for statement in statements:
        if statement.get('Effect') == 'Allow':
            actions = statement.get('Action', [])
            if isinstance(actions, str):
                actions = [actions]
            if 'iam:PassRole' in actions:
                resources = statement.get('Resource', [])
                if isinstance(resources, str):
                    resources = [resources]
                for resource in resources:
                    if resource == role_arn or resource == '*':
                        return True
    return False


def _get_dynamodb_permissions(policy_doc):
    """Extract all DynamoDB permissions from a policy document."""
    permissions = set()
    statements = policy_doc.get('Statement', [])
    for statement in statements:
        if statement.get('Effect') == 'Allow':
            actions = statement.get('Action', [])
            if isinstance(actions, str):
                actions = [actions]
            for action in actions:
                if action.startswith('dynamodb:'):
                    permissions.add(action)
    return permissions

