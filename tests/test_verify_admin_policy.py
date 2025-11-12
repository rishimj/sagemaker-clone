"""
Test to verify that all services use MLPlatformAdminPolicy.

This test checks that:
1. MLPlatformAdminPolicy exists
2. Lambda role has MLPlatformAdminPolicy attached
3. ECS Task role has MLPlatformAdminPolicy attached
4. ECS Execution role has the AWS managed policy (correct)
"""

import pytest
import boto3
import os
from dotenv import load_dotenv

load_dotenv()

# Test configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
AWS_ACCOUNT_ID = os.getenv('AWS_ACCOUNT_ID')

# Use real AWS if credentials are available
USE_REAL_AWS = os.getenv('AWS_ACCESS_KEY_ID') and AWS_ACCOUNT_ID

ADMIN_POLICY_NAME = 'MLPlatformAdminPolicy'
ADMIN_POLICY_ARN = f"arn:aws:iam::{AWS_ACCOUNT_ID}:policy/{ADMIN_POLICY_NAME}" if AWS_ACCOUNT_ID else None

LAMBDA_ROLE_NAME = 'MLPlatformLambdaRole'
ECS_TASK_ROLE_NAME = 'MLPlatformECSTaskRole'
ECS_EXECUTION_ROLE_NAME = 'MLPlatformECSTaskExecutionRole'


@pytest.fixture
def iam_client():
    """Create IAM client."""
    if USE_REAL_AWS:
        return boto3.client('iam', region_name=AWS_REGION)
    else:
        pytest.skip("Real AWS credentials not available")


@pytest.mark.skipif(not USE_REAL_AWS, reason="Requires real AWS credentials")
class TestAdminPolicyUsage:
    """Test that all services use MLPlatformAdminPolicy."""
    
    def test_admin_policy_exists(self, iam_client):
        """Test that MLPlatformAdminPolicy exists."""
        if not ADMIN_POLICY_ARN:
            pytest.skip("AWS_ACCOUNT_ID not set")
        
        try:
            response = iam_client.get_policy(PolicyArn=ADMIN_POLICY_ARN)
            assert response['Policy']['PolicyName'] == ADMIN_POLICY_NAME
            print(f"✓ MLPlatformAdminPolicy exists: {ADMIN_POLICY_ARN}")
        except iam_client.exceptions.NoSuchEntityException:
            pytest.fail(f"MLPlatformAdminPolicy does not exist. Create it using infrastructure/MLPlatformAdminPolicy.json")
        except Exception as e:
            if 'AccessDenied' in str(e):
                pytest.skip(f"Insufficient permissions to check policy: {e}")
            raise
    
    def test_lambda_role_has_admin_policy(self, iam_client):
        """Test that Lambda role has MLPlatformAdminPolicy attached."""
        if not ADMIN_POLICY_ARN:
            pytest.skip("AWS_ACCOUNT_ID not set")
        
        try:
            response = iam_client.list_attached_role_policies(RoleName=LAMBDA_ROLE_NAME)
            policy_arns = [p['PolicyArn'] for p in response['AttachedPolicies']]
            
            has_admin_policy = ADMIN_POLICY_ARN in policy_arns
            
            if has_admin_policy:
                print(f"✓ MLPlatformLambdaRole has MLPlatformAdminPolicy attached")
            else:
                print(f"⚠️  MLPlatformLambdaRole does NOT have MLPlatformAdminPolicy")
                print(f"   Current policies: {policy_arns}")
                pytest.fail(f"MLPlatformLambdaRole should have MLPlatformAdminPolicy attached. "
                          f"Run: ./infrastructure/setup_iam_roles_simple.sh")
            
            assert has_admin_policy, f"Lambda role should have {ADMIN_POLICY_NAME} attached"
        except iam_client.exceptions.NoSuchEntityException:
            pytest.fail(f"Lambda role {LAMBDA_ROLE_NAME} does not exist")
        except Exception as e:
            if 'AccessDenied' in str(e):
                pytest.skip(f"Insufficient permissions to check role policies: {e}")
            raise
    
    def test_ecs_task_role_has_admin_policy(self, iam_client):
        """Test that ECS Task role has MLPlatformAdminPolicy attached."""
        if not ADMIN_POLICY_ARN:
            pytest.skip("AWS_ACCOUNT_ID not set")
        
        try:
            response = iam_client.list_attached_role_policies(RoleName=ECS_TASK_ROLE_NAME)
            policy_arns = [p['PolicyArn'] for p in response['AttachedPolicies']]
            
            has_admin_policy = ADMIN_POLICY_ARN in policy_arns
            
            if has_admin_policy:
                print(f"✓ MLPlatformECSTaskRole has MLPlatformAdminPolicy attached")
            else:
                print(f"⚠️  MLPlatformECSTaskRole does NOT have MLPlatformAdminPolicy")
                print(f"   Current policies: {policy_arns}")
                pytest.fail(f"ECS Task role should have MLPlatformAdminPolicy attached. "
                          f"Run: ./infrastructure/setup_iam_roles_simple.sh")
            
            assert has_admin_policy, f"ECS Task role should have {ADMIN_POLICY_NAME} attached"
        except iam_client.exceptions.NoSuchEntityException:
            pytest.fail(f"ECS Task role {ECS_TASK_ROLE_NAME} does not exist")
        except Exception as e:
            if 'AccessDenied' in str(e):
                pytest.skip(f"Insufficient permissions to check role policies: {e}")
            raise
    
    def test_ecs_execution_role_has_aws_managed_policy(self, iam_client):
        """Test that ECS Execution role has AWS managed policy (correct setup)."""
        try:
            response = iam_client.list_attached_role_policies(RoleName=ECS_EXECUTION_ROLE_NAME)
            policy_arns = [p['PolicyArn'] for p in response['AttachedPolicies']]
            
            has_aws_policy = any('AmazonECSTaskExecutionRolePolicy' in arn for arn in policy_arns)
            
            if has_aws_policy:
                print(f"✓ MLPlatformECSTaskExecutionRole has AmazonECSTaskExecutionRolePolicy (correct)")
            else:
                print(f"⚠️  MLPlatformECSTaskExecutionRole does NOT have AWS managed policy")
                print(f"   Current policies: {policy_arns}")
            
            # Note: ECS Execution role should NOT have MLPlatformAdminPolicy
            # It should only have the AWS managed policy
            has_admin_policy = ADMIN_POLICY_ARN in policy_arns if ADMIN_POLICY_ARN else False
            if has_admin_policy:
                print(f"   Note: ECS Execution role also has MLPlatformAdminPolicy (unusual but OK)")
            
            assert has_aws_policy, "ECS Execution role should have AmazonECSTaskExecutionRolePolicy"
        except iam_client.exceptions.NoSuchEntityException:
            pytest.fail(f"ECS Execution role {ECS_EXECUTION_ROLE_NAME} does not exist")
        except Exception as e:
            if 'AccessDenied' in str(e):
                pytest.skip(f"Insufficient permissions to check role policies: {e}")
            raise
    
    def test_all_services_use_same_admin_policy(self, iam_client):
        """Test that Lambda and ECS Task roles both use MLPlatformAdminPolicy."""
        if not ADMIN_POLICY_ARN:
            pytest.skip("AWS_ACCOUNT_ID not set")
        
        try:
            # Check Lambda role
            lambda_response = iam_client.list_attached_role_policies(RoleName=LAMBDA_ROLE_NAME)
            lambda_policies = [p['PolicyArn'] for p in lambda_response['AttachedPolicies']]
            lambda_has_admin = ADMIN_POLICY_ARN in lambda_policies
            
            # Check ECS Task role
            ecs_response = iam_client.list_attached_role_policies(RoleName=ECS_TASK_ROLE_NAME)
            ecs_policies = [p['PolicyArn'] for p in ecs_response['AttachedPolicies']]
            ecs_has_admin = ADMIN_POLICY_ARN in ecs_policies
            
            if lambda_has_admin and ecs_has_admin:
                print(f"✓ Both Lambda and ECS Task roles use MLPlatformAdminPolicy")
            else:
                print(f"⚠️  Not all services use MLPlatformAdminPolicy:")
                print(f"   Lambda role: {'✓' if lambda_has_admin else '✗'}")
                print(f"   ECS Task role: {'✓' if ecs_has_admin else '✗'}")
            
            assert lambda_has_admin and ecs_has_admin, \
                "Both Lambda and ECS Task roles should have MLPlatformAdminPolicy attached"
        except Exception as e:
            if 'AccessDenied' in str(e):
                pytest.skip(f"Insufficient permissions: {e}")
            raise

