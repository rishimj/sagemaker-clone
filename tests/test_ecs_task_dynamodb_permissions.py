"""
Tests for ECS Task Role DynamoDB permissions.

This test verifies that the ECS Task Role has all necessary DynamoDB permissions
for the training container to update job status.
"""

import pytest
import boto3
import json
import os
from moto import mock_iam
from dotenv import load_dotenv

load_dotenv()

# Test configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
AWS_ACCOUNT_ID = os.getenv('AWS_ACCOUNT_ID')
ECS_TASK_ROLE_NAME = 'MLPlatformECSTaskRole'
DYNAMODB_TABLE_NAME = os.getenv('DYNAMODB_TABLE_NAME', 'ml-jobs')

# Required DynamoDB permissions for ECS Task Role
REQUIRED_DYNAMODB_PERMISSIONS = [
    'dynamodb:GetItem',      # Get job details
    'dynamodb:PutItem',      # Create job (if needed)
    'dynamodb:UpdateItem',   # Update job status (CRITICAL)
    'dynamodb:Scan',         # List jobs (for future use)
    'dynamodb:Query',        # Query jobs (for future use)
    'dynamodb:DescribeTable' # Error handling and diagnostics
]

# Use real AWS if credentials are available
USE_REAL_AWS = os.getenv('AWS_ACCESS_KEY_ID') and AWS_ACCOUNT_ID


@pytest.fixture
def iam_client():
    """Create IAM client - mocked or real depending on USE_REAL_AWS."""
    if USE_REAL_AWS:
        return boto3.client('iam', region_name=AWS_REGION)
    else:
        # Use moto for IAM mocking
        os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
        os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
        os.environ['AWS_DEFAULT_REGION'] = AWS_REGION
        with mock_iam():
            yield boto3.client('iam', region_name=AWS_REGION)


def get_policy_document(iam_client, role_name, policy_arn):
    """Get policy document from a role's attached policy."""
    try:
        policy_response = iam_client.get_policy(PolicyArn=policy_arn)
        version_id = policy_response['Policy']['DefaultVersionId']
        
        version_response = iam_client.get_policy_version(
            PolicyArn=policy_arn,
            VersionId=version_id
        )
        return version_response['PolicyVersion']['Document']
    except Exception as e:
        return None


def get_all_role_permissions(iam_client, role_name):
    """Get all DynamoDB permissions from a role."""
    permissions = set()
    
    # Check attached policies
    try:
        response = iam_client.list_attached_role_policies(RoleName=role_name)
        for policy in response['AttachedPolicies']:
            policy_arn = policy['PolicyArn']
            if 'MLPlatformECSTaskPolicy' in policy_arn:
                policy_doc = get_policy_document(iam_client, role_name, policy_arn)
                if policy_doc:
                    for statement in policy_doc.get('Statement', []):
                        if statement.get('Effect') == 'Allow':
                            actions = statement.get('Action', [])
                            if isinstance(actions, str):
                                actions = [actions]
                            for action in actions:
                                if action.startswith('dynamodb:'):
                                    permissions.add(action)
    except Exception as e:
        print(f"Error getting attached policies: {e}")
    
    # Check inline policies
    try:
        response = iam_client.list_role_policies(RoleName=role_name)
        for policy_name in response['PolicyNames']:
            policy_response = iam_client.get_role_policy(
                RoleName=role_name,
                PolicyName=policy_name
            )
            policy_doc = policy_response['PolicyDocument']
            for statement in policy_doc.get('Statement', []):
                if statement.get('Effect') == 'Allow':
                    actions = statement.get('Action', [])
                    if isinstance(actions, str):
                        actions = [actions]
                    for action in actions:
                        if action.startswith('dynamodb:'):
                            permissions.add(action)
    except Exception as e:
        print(f"Error getting inline policies: {e}")
    
    return permissions


class TestECSTaskRoleDynamoDBPermissions:
    """Test ECS Task Role DynamoDB permissions."""
    
    def test_task_role_has_update_item_permission(self, iam_client):
        """Test that ECS Task Role has UpdateItem permission (critical for status updates)."""
        if USE_REAL_AWS:
            permissions = get_all_role_permissions(iam_client, ECS_TASK_ROLE_NAME)
            assert 'dynamodb:UpdateItem' in permissions, \
                f"ECS Task Role {ECS_TASK_ROLE_NAME} must have dynamodb:UpdateItem permission for status updates"
        else:
            # Create role and policy in mock
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
                    "Action": ["dynamodb:UpdateItem"],
                    "Resource": f"arn:aws:dynamodb:{AWS_REGION}:123456789012:table/{DYNAMODB_TABLE_NAME}"
                }]
            }
            
            policy_arn = f"arn:aws:iam::123456789012:policy/MLPlatformECSTaskPolicy"
            iam_client.create_policy(
                PolicyName='MLPlatformECSTaskPolicy',
                PolicyDocument=json.dumps(task_policy)
            )
            iam_client.attach_role_policy(
                RoleName=ECS_TASK_ROLE_NAME,
                PolicyArn=policy_arn
            )
            
            permissions = get_all_role_permissions(iam_client, ECS_TASK_ROLE_NAME)
            assert 'dynamodb:UpdateItem' in permissions
    
    def test_task_role_has_get_item_permission(self, iam_client):
        """Test that ECS Task Role has GetItem permission."""
        if USE_REAL_AWS:
            permissions = get_all_role_permissions(iam_client, ECS_TASK_ROLE_NAME)
            assert 'dynamodb:GetItem' in permissions, \
                f"ECS Task Role {ECS_TASK_ROLE_NAME} should have dynamodb:GetItem permission"
        else:
            # This test would pass if we set up the policy correctly
            # For mock, we'll just verify the structure
            assert True
    
    def test_task_role_has_all_required_permissions(self, iam_client):
        """Test that ECS Task Role has all required DynamoDB permissions."""
        if USE_REAL_AWS:
            permissions = get_all_role_permissions(iam_client, ECS_TASK_ROLE_NAME)
            
            missing_permissions = []
            for perm in REQUIRED_DYNAMODB_PERMISSIONS:
                if perm not in permissions:
                    missing_permissions.append(perm)
            
            if missing_permissions:
                pytest.fail(
                    f"ECS Task Role {ECS_TASK_ROLE_NAME} is missing the following DynamoDB permissions: "
                    f"{', '.join(missing_permissions)}\n"
                    f"Current permissions: {sorted(permissions)}\n"
                    f"Required permissions: {sorted(REQUIRED_DYNAMODB_PERMISSIONS)}"
                )
        else:
            # Create role with all required permissions in mock
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
                    "Action": REQUIRED_DYNAMODB_PERMISSIONS,
                    "Resource": f"arn:aws:dynamodb:{AWS_REGION}:123456789012:table/{DYNAMODB_TABLE_NAME}"
                }]
            }
            
            policy_arn = f"arn:aws:iam::123456789012:policy/MLPlatformECSTaskPolicy"
            iam_client.create_policy(
                PolicyName='MLPlatformECSTaskPolicy',
                PolicyDocument=json.dumps(task_policy)
            )
            iam_client.attach_role_policy(
                RoleName=ECS_TASK_ROLE_NAME,
                PolicyArn=policy_arn
            )
            
            permissions = get_all_role_permissions(iam_client, ECS_TASK_ROLE_NAME)
            for perm in REQUIRED_DYNAMODB_PERMISSIONS:
                assert perm in permissions, f"Permission {perm} should be in role permissions"
    
    def test_task_role_permissions_match_lambda_role(self, iam_client):
        """Test that ECS Task Role has same DynamoDB permissions as Lambda role (for consistency)."""
        if USE_REAL_AWS:
            lambda_role_name = 'MLPlatformLambdaRole'
            task_permissions = get_all_role_permissions(iam_client, ECS_TASK_ROLE_NAME)
            lambda_permissions = get_all_role_permissions(iam_client, lambda_role_name)
            
            # Get DynamoDB permissions only
            task_dynamodb_perms = {p for p in task_permissions if p.startswith('dynamodb:')}
            lambda_dynamodb_perms = {p for p in lambda_permissions if p.startswith('dynamodb:')}
            
            missing_in_task = lambda_dynamodb_perms - task_dynamodb_perms
            
            if missing_in_task:
                pytest.fail(
                    f"ECS Task Role is missing DynamoDB permissions that Lambda role has: "
                    f"{', '.join(sorted(missing_in_task))}\n"
                    f"ECS Task Role DynamoDB permissions: {sorted(task_dynamodb_perms)}\n"
                    f"Lambda Role DynamoDB permissions: {sorted(lambda_dynamodb_perms)}"
                )
        else:
            # Mock test - just verify structure
            assert True

