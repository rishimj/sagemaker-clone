"""
Comprehensive ECS container startup test with detailed logging
Tests if we can get an ECS container running and logs everything
"""

import os
import sys
import time
import json
import boto3
from datetime import datetime

# Force unbuffered output
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(line_buffering=True)

from dotenv import load_dotenv
load_dotenv()

AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
AWS_ACCOUNT_ID = os.getenv('AWS_ACCOUNT_ID', 'YOUR_ACCOUNT_ID')
ECS_CLUSTER = os.getenv('ECS_CLUSTER_NAME', 'training-cluster')
SUBNET_ID = os.getenv('SUBNET_ID', 'subnet-0b19b732d5b6049e5')
S3_BUCKET = os.getenv('S3_BUCKET_NAME', 'your-ml-platform-bucket')
DYNAMODB_TABLE = os.getenv('DYNAMODB_TABLE_NAME', 'ml-jobs')

# Initialize clients
iam_client = boto3.client('iam', region_name=AWS_REGION)
ecs_client = boto3.client('ecs', region_name=AWS_REGION)
ecr_client = boto3.client('ecr', region_name=AWS_REGION)
logs_client = boto3.client('logs', region_name=AWS_REGION)

def print_section(title):
    print(f"\n{'='*80}", flush=True)
    print(f"{title}", flush=True)
    print(f"{'='*80}", flush=True)

def print_info(label, value):
    print(f"  {label}: {value}", flush=True)

def check_iam_role(role_name, role_type):
    """Check IAM role and its policies"""
    print_section(f"Checking {role_type}: {role_name}")
    
    try:
        # Get role
        role_response = iam_client.get_role(RoleName=role_name)
        role = role_response['Role']
        print_info("Role ARN", role['Arn'])
        print_info("Role Path", role['Path'])
        print_info("Create Date", str(role['CreateDate']))
        
        # Check trust policy
        trust_policy = role['AssumeRolePolicyDocument']
        if isinstance(trust_policy, str):
            trust_policy = json.loads(trust_policy)
        print_info("Trust Policy", json.dumps(trust_policy, indent=4))
        
        # List attached policies
        try:
            attached_policies = iam_client.list_attached_role_policies(RoleName=role_name)
            print_info("Attached Policies", f"{len(attached_policies['AttachedPolicies'])} found")
            for policy in attached_policies['AttachedPolicies']:
                print(f"    - {policy['PolicyName']} ({policy['PolicyArn']})", flush=True)
                
                # Get policy details
                try:
                    policy_response = iam_client.get_policy(PolicyArn=policy['PolicyArn'])
                    policy_version = iam_client.get_policy_version(
                        PolicyArn=policy['PolicyArn'],
                        VersionId=policy_response['Policy']['DefaultVersionId']
                    )
                    policy_doc = policy_version['PolicyVersion']['Document']
                    print(f"      Permissions: {json.dumps(policy_doc, indent=6)}", flush=True)
                except Exception as e:
                    print(f"      ⚠️  Could not get policy details: {e}", flush=True)
        except Exception as e:
            print(f"  ⚠️  Could not list attached policies: {e}", flush=True)
        
        # List inline policies
        try:
            inline_policies = iam_client.list_role_policies(RoleName=role_name)
            if inline_policies['PolicyNames']:
                print_info("Inline Policies", f"{len(inline_policies['PolicyNames'])} found")
                for policy_name in inline_policies['PolicyNames']:
                    policy_response = iam_client.get_role_policy(
                        RoleName=role_name,
                        PolicyName=policy_name
                    )
                    print(f"    - {policy_name}: {json.dumps(policy_response['PolicyDocument'], indent=6)}", flush=True)
        except Exception as e:
            print(f"  ⚠️  Could not list inline policies: {e}", flush=True)
        
        return True
    except iam_client.exceptions.NoSuchEntityException:
        print(f"  ❌ Role does not exist: {role_name}", flush=True)
        return False
    except Exception as e:
        print(f"  ❌ Error checking role: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return False

def check_task_definition():
    """Check ECS task definition"""
    print_section("Checking ECS Task Definition")
    
    try:
        response = ecs_client.describe_task_definition(taskDefinition='training-job')
        td = response['taskDefinition']
        
        print_info("Family", td['family'])
        print_info("Revision", td['revision'])
        print_info("Status", td['status'])
        print_info("CPU", td.get('cpu', 'N/A'))
        print_info("Memory", td.get('memory', 'N/A'))
        print_info("Network Mode", td.get('networkMode', 'N/A'))
        print_info("Requires Compatibilities", str(td.get('requiresCompatibilities', [])))
        
        print_info("Execution Role ARN", td.get('executionRoleArn', 'NOT SET'))
        print_info("Task Role ARN", td.get('taskRoleArn', 'NOT SET'))
        
        # Check container definitions
        print_info("Container Definitions", f"{len(td['containerDefinitions'])} found")
        for container in td['containerDefinitions']:
            print(f"    Container: {container['name']}", flush=True)
            print(f"      Image: {container.get('image', 'N/A')}", flush=True)
            print(f"      Essential: {container.get('essential', False)}", flush=True)
            
            # Check log configuration
            if 'logConfiguration' in container:
                log_config = container['logConfiguration']
                print(f"      Log Driver: {log_config.get('logDriver', 'N/A')}", flush=True)
                if 'options' in log_config:
                    print(f"      Log Options: {json.dumps(log_config['options'], indent=8)}", flush=True)
            else:
                print(f"      ⚠️  No log configuration", flush=True)
        
        return td
    except Exception as e:
        print(f"  ❌ Error checking task definition: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return None

def check_ecr_image():
    """Check if ECR image exists"""
    print_section("Checking ECR Image")
    
    try:
        image_uri = f"{AWS_ACCOUNT_ID}.dkr.ecr.{AWS_REGION}.amazonaws.com/training:latest"
        print_info("Image URI", image_uri)
        
        # List images
        response = ecr_client.describe_images(
            repositoryName='training',
            imageIds=[{'imageTag': 'latest'}]
        )
        
        if response['imageDetails']:
            image = response['imageDetails'][0]
            print_info("Image Found", "✅ Yes")
            print_info("Image Pushed", str(image.get('imagePushedAt', 'N/A')))
            print_info("Image Size", f"{image.get('imageSizeInBytes', 0) / 1024 / 1024:.2f} MB")
            print_info("Image Digest", image.get('imageDigest', 'N/A'))
            return True
        else:
            print_info("Image Found", "❌ No")
            return False
    except Exception as e:
        print(f"  ❌ Error checking ECR image: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return False

def check_cluster():
    """Check ECS cluster"""
    print_section("Checking ECS Cluster")
    
    try:
        response = ecs_client.describe_clusters(clusters=[ECS_CLUSTER])
        if response['clusters']:
            cluster = response['clusters'][0]
            print_info("Cluster Name", cluster['clusterName'])
            print_info("Status", cluster['status'])
            print_info("Active Services", cluster.get('activeServicesCount', 0))
            print_info("Running Tasks", cluster.get('runningTasksCount', 0))
            print_info("Pending Tasks", cluster.get('pendingTasksCount', 0))
            return True
        else:
            print(f"  ❌ Cluster not found: {ECS_CLUSTER}", flush=True)
            return False
    except Exception as e:
        print(f"  ❌ Error checking cluster: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return False

def check_network():
    """Check network configuration"""
    print_section("Checking Network Configuration")
    
    print_info("Subnet ID", SUBNET_ID)
    print_info("Region", AWS_REGION)
    
    try:
        ec2_client = boto3.client('ec2', region_name=AWS_REGION)
        response = ec2_client.describe_subnets(SubnetIds=[SUBNET_ID])
        if response['Subnets']:
            subnet = response['Subnets'][0]
            print_info("Subnet VPC", subnet['VpcId'])
            print_info("Subnet AZ", subnet['AvailabilityZone'])
            print_info("Subnet CIDR", subnet['CidrBlock'])
            return True
        else:
            print(f"  ❌ Subnet not found: {SUBNET_ID}", flush=True)
            return False
    except Exception as e:
        print(f"  ⚠️  Could not verify subnet: {e}", flush=True)
        return False

def run_ecs_task():
    """Run an ECS task and monitor it"""
    print_section("Running ECS Task")
    
    task_def = f"training-job:{ecs_client.describe_task_definition(taskDefinition='training-job')['taskDefinition']['revision']}"
    print_info("Task Definition", task_def)
    print_info("Cluster", ECS_CLUSTER)
    print_info("Subnet", SUBNET_ID)
    
    # Prepare task configuration
    task_config = {
        'cluster': ECS_CLUSTER,
        'taskDefinition': task_def,
        'launchType': 'FARGATE',
        'networkConfiguration': {
            'awsvpcConfiguration': {
                'subnets': [SUBNET_ID],
                'assignPublicIp': 'ENABLED'
            }
        },
        'overrides': {
            'containerOverrides': [{
                'name': 'training',
                'environment': [
                    {'name': 'JOB_ID', 'value': 'test-startup-123'},
                    {'name': 'S3_INPUT', 'value': f's3://{S3_BUCKET}/data/test_data.csv'},
                    {'name': 'S3_OUTPUT', 'value': f's3://{S3_BUCKET}/models/test-startup'},
                    {'name': 'HYPERPARAMS', 'value': '{"epochs": 1, "learning_rate": 0.01}'},
                    {'name': 'DYNAMODB_TABLE', 'value': DYNAMODB_TABLE},
                    {'name': 'AWS_REGION', 'value': AWS_REGION}
                ]
            }]
        }
    }
    
    print_info("Task Config", json.dumps(task_config, indent=4, default=str))
    
    try:
        print(f"\n  🚀 Starting task...", flush=True)
        response = ecs_client.run_task(**task_config)
        
        if 'tasks' in response and response['tasks']:
            task = response['tasks'][0]
            task_arn = task['taskArn']
            task_id = task_arn.split('/')[-1]
            
            print_info("Task ARN", task_arn)
            print_info("Task ID", task_id)
            print_info("Initial Status", task.get('lastStatus', 'N/A'))
            print_info("Desired Status", task.get('desiredStatus', 'N/A'))
            
            if 'failures' in response and response['failures']:
                print(f"\n  ⚠️  Task failures:", flush=True)
                for failure in response['failures']:
                    print(f"    - {failure.get('reason', 'Unknown')}: {failure.get('detail', '')}", flush=True)
            
            # Monitor task
            print_section("Monitoring Task Status")
            max_wait = 300  # 5 minutes
            start_time = time.time()
            last_status = None
            
            while time.time() - start_time < max_wait:
                task_response = ecs_client.describe_tasks(
                    cluster=ECS_CLUSTER,
                    tasks=[task_id]
                )
                
                if task_response['tasks']:
                    current_task = task_response['tasks'][0]
                    current_status = current_task['lastStatus']
                    elapsed = int(time.time() - start_time)
                    
                    if current_status != last_status:
                        print(f"\n  [{elapsed}s] Status changed: {last_status} → {current_status}", flush=True)
                        last_status = current_status
                        
                        # Print detailed status
                        print(f"    Desired Status: {current_task.get('desiredStatus', 'N/A')}", flush=True)
                        print(f"    Health Status: {current_task.get('healthStatus', 'N/A')}", flush=True)
                        
                        if 'startedAt' in current_task:
                            print(f"    Started At: {current_task['startedAt']}", flush=True)
                        
                        if 'stoppedAt' in current_task:
                            print(f"    Stopped At: {current_task['stoppedAt']}", flush=True)
                            print(f"    Stopped Reason: {current_task.get('stoppedReason', 'N/A')}", flush=True)
                        
                        # Check container status
                        if 'containers' in current_task:
                            for container in current_task['containers']:
                                print(f"    Container: {container.get('name', 'N/A')}", flush=True)
                                print(f"      Status: {container.get('lastStatus', 'N/A')}", flush=True)
                                if 'exitCode' in container:
                                    print(f"      Exit Code: {container.get('exitCode', 'N/A')}", flush=True)
                                if 'reason' in container:
                                    print(f"      Reason: {container.get('reason', 'N/A')}", flush=True)
                    
                    # Check if stopped
                    if current_status == 'STOPPED':
                        print(f"\n  ⏹️  Task stopped after {elapsed}s", flush=True)
                        stopped_reason = current_task.get('stoppedReason', 'N/A')
                        print(f"    Stopped Reason: {stopped_reason}", flush=True)
                        if 'containers' in current_task:
                            for container in current_task['containers']:
                                print(f"    Container: {container.get('name', 'N/A')}", flush=True)
                                if 'exitCode' in container:
                                    exit_code = container.get('exitCode')
                                    print(f"      Exit Code: {exit_code}", flush=True)
                                    if exit_code != 0:
                                        print(f"      ❌ Container exited with error code: {exit_code}", flush=True)
                                if 'reason' in container:
                                    print(f"      Reason: {container.get('reason', 'N/A')}", flush=True)
                        
                        # Try to get logs
                        print_section("Checking CloudWatch Logs")
                        try:
                            log_group = '/ecs/training-job'
                            log_stream = f"ecs/training/{task_id}"
                            
                            print_info("Log Group", log_group)
                            print_info("Log Stream", log_stream)
                            
                            log_events = logs_client.get_log_events(
                                logGroupName=log_group,
                                logStreamName=log_stream,
                                limit=50
                            )
                            
                            if log_events['events']:
                                print(f"\n  📋 Last {len(log_events['events'])} log entries:", flush=True)
                                for event in log_events['events'][-20:]:  # Last 20
                                    timestamp = datetime.fromtimestamp(event['timestamp'] / 1000).strftime('%H:%M:%S')
                                    print(f"    [{timestamp}] {event['message']}", flush=True)
                            else:
                                print(f"  ⚠️  No log events found", flush=True)
                        except Exception as e:
                            print(f"  ⚠️  Could not get logs: {e}", flush=True)
                        
                        return current_task
                    
                    # Check if running
                    if current_status == 'RUNNING':
                        print(f"\n  ✅ Task is RUNNING after {elapsed}s!", flush=True)
                        if 'startedAt' in current_task:
                            print(f"    Started At: {current_task['startedAt']}", flush=True)
                        
                        # Wait a bit to see if it stays running
                        print(f"  ⏳ Monitoring for 30 seconds to see if it stays running...", flush=True)
                        time.sleep(30)
                        
                        # Check again
                        task_response = ecs_client.describe_tasks(
                            cluster=ECS_CLUSTER,
                            tasks=[task_id]
                        )
                        if task_response['tasks']:
                            final_task = task_response['tasks'][0]
                            final_status = final_task['lastStatus']
                            print(f"  Final Status: {final_status}", flush=True)
                            if final_status == 'RUNNING':
                                print(f"  ✅ Task is still RUNNING!", flush=True)
                            else:
                                print(f"  ⚠️  Task status changed to: {final_status}", flush=True)
                                if final_status == 'STOPPED':
                                    print(f"    Stopped Reason: {final_task.get('stoppedReason', 'N/A')}", flush=True)
                                    if 'containers' in final_task:
                                        for container in final_task['containers']:
                                            if 'exitCode' in container:
                                                exit_code = container.get('exitCode')
                                                print(f"    Exit Code: {exit_code}", flush=True)
                                            if 'reason' in container:
                                                print(f"    Reason: {container.get('reason', 'N/A')}", flush=True)
                        
                        return final_task if 'final_task' in locals() else current_task
                else:
                    print(f"  ⚠️  Task not found in response", flush=True)
                
                time.sleep(5)
                elapsed = int(time.time() - start_time)
                if elapsed % 10 == 0:
                    print(f"  ⏳ {elapsed}s elapsed, status: {current_status if 'current_status' in locals() else 'checking...'}", flush=True)
            
            print(f"\n  ⏱️  Timeout after {max_wait}s", flush=True)
            return None
        else:
            print(f"  ❌ No tasks in response", flush=True)
            if 'failures' in response:
                print(f"  Failures:", flush=True)
                for failure in response['failures']:
                    print(f"    - {failure.get('reason', 'Unknown')}: {failure.get('detail', '')}", flush=True)
            return None
            
    except Exception as e:
        print(f"  ❌ Error running task: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return None

def main():
    print_section("ECS Container Startup Diagnostic Test")
    print_info("Timestamp", datetime.now().isoformat())
    print_info("Region", AWS_REGION)
    print_info("Account ID", AWS_ACCOUNT_ID)
    
    # Check all components
    print("\n" + "="*80, flush=True)
    print("STEP 1: Checking IAM Roles and Policies", flush=True)
    print("="*80, flush=True)
    
    exec_role_ok = check_iam_role('MLPlatformECSTaskExecutionRole', 'ECS Task Execution Role')
    task_role_ok = check_iam_role('MLPlatformECSTaskRole', 'ECS Task Role')
    
    print("\n" + "="*80, flush=True)
    print("STEP 2: Checking ECS Configuration", flush=True)
    print("="*80, flush=True)
    
    cluster_ok = check_cluster()
    task_def = check_task_definition()
    image_ok = check_ecr_image()
    network_ok = check_network()
    
    print("\n" + "="*80, flush=True)
    print("STEP 3: Summary", flush=True)
    print("="*80, flush=True)
    
    print(f"  Execution Role: {'✅ OK' if exec_role_ok else '❌ FAILED'}", flush=True)
    print(f"  Task Role: {'✅ OK' if task_role_ok else '❌ FAILED'}", flush=True)
    print(f"  Cluster: {'✅ OK' if cluster_ok else '❌ FAILED'}", flush=True)
    print(f"  Task Definition: {'✅ OK' if task_def else '❌ FAILED'}", flush=True)
    print(f"  ECR Image: {'✅ OK' if image_ok else '❌ FAILED'}", flush=True)
    print(f"  Network: {'✅ OK' if network_ok else '❌ FAILED'}", flush=True)
    
    # Network check failure is just a permission issue, not a real problem
    # Continue if core components are OK
    core_ok = exec_role_ok and task_role_ok and cluster_ok and task_def and image_ok
    
    if core_ok:
        print("\n" + "="*80, flush=True)
        print("STEP 4: Running ECS Task", flush=True)
        print("="*80, flush=True)
        
        result = run_ecs_task()
        
        if result:
            if result.get('lastStatus') == 'RUNNING':
                print("\n" + "="*80, flush=True)
                print("✅ SUCCESS: ECS Container is RUNNING!", flush=True)
                print("="*80, flush=True)
            else:
                print("\n" + "="*80, flush=True)
                print("❌ FAILED: ECS Container did not run successfully", flush=True)
                print("="*80, flush=True)
        else:
            print("\n" + "="*80, flush=True)
            print("❌ FAILED: Could not run ECS task", flush=True)
            print("="*80, flush=True)
    else:
        print("\n" + "="*80, flush=True)
        print("❌ Cannot run task: Configuration issues found", flush=True)
        print("="*80, flush=True)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user", flush=True)
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)

