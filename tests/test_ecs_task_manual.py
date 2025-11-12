"""
Manual test to start an ECS task and see what errors occur
"""

import os
import json
import boto3
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
ECS_CLUSTER = os.getenv('ECS_CLUSTER_NAME', 'training-cluster')
SUBNET_ID = os.getenv('SUBNET_ID')
S3_BUCKET = os.getenv('S3_BUCKET_NAME', 'your-ml-platform-bucket')

ecs = boto3.client('ecs', region_name=AWS_REGION)

print("Testing ECS task startup...")
print(f"Cluster: {ECS_CLUSTER}")
print(f"Subnet: {SUBNET_ID}")
print(f"Region: {AWS_REGION}")

try:
    response = ecs.run_task(
        cluster=ECS_CLUSTER,
        taskDefinition='training-job',
        launchType='FARGATE',
        networkConfiguration={
            'awsvpcConfiguration': {
                'subnets': [SUBNET_ID],
                'assignPublicIp': 'ENABLED'
            }
        },
        overrides={
            'containerOverrides': [{
                'name': 'training',
                # Note: Cannot override image in Fargate - must use task definition image
                'environment': [
                    {'name': 'JOB_ID', 'value': 'test-manual-001'},
                    {'name': 'S3_INPUT', 'value': f's3://{S3_BUCKET}/data/test_data.csv'},
                    {'name': 'S3_OUTPUT', 'value': f's3://{S3_BUCKET}/models/test-manual'},
                    {'name': 'HYPERPARAMS', 'value': json.dumps({'epochs': 5, 'learning_rate': 0.01})}
                ]
            }]
        }
    )
    
    print("\n✅ Task started successfully!")
    print(f"Task ARN: {response['tasks'][0]['taskArn']}")
    print(f"Task Status: {response['tasks'][0]['lastStatus']}")
    
    if 'failures' in response and response['failures']:
        print("\n❌ Failures:")
        for failure in response['failures']:
            print(f"  - {failure}")
            
except Exception as e:
    print(f"\n❌ Error starting task: {e}")
    import traceback
    traceback.print_exc()

