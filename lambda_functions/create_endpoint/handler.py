import boto3
import json
import os
import sys

# Add current directory to path for Lambda packaging
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
sys.path.append('/opt')  # For Lambda layers

try:
    from storage.logger import get_lambda_logger
    from storage.endpoint_store import EndpointStore
except ImportError as e:
    # Fallback for import errors
    import logging
    logging.basicConfig(level=logging.ERROR)
    logger = logging.getLogger(__name__)
    logger.error(f"Error importing modules: {e}", exc_info=True)
    raise

# Get region from environment or use default
region = os.environ.get('AWS_REGION', 'us-east-1')

# Initialize clients with explicit region
dynamodb = boto3.resource('dynamodb', region_name=region)
ecs = boto3.client('ecs', region_name=region)
s3 = boto3.client('s3', region_name=region)
elbv2 = boto3.client('elbv2', region_name=region)
autoscaling = boto3.client('application-autoscaling', region_name=region)

# Initialize logger
logger = get_lambda_logger({'service': 'create_endpoint', 'region': region})
logger.info("Initialized boto3 clients", extra={'region': region})

# Initialize endpoint store with environment variable
endpoints_table = os.environ.get('ENDPOINTS_TABLE', 'ml-endpoints')
logger.info("Initializing EndpointStore", extra={'table': endpoints_table})

try:
    endpoint_store = EndpointStore(endpoints_table, dynamodb)
    logger.info("EndpointStore initialized successfully", extra={'table_name': endpoint_store.table.table_name})
except Exception as e:
    logger.error("Failed to initialize EndpointStore", exc_info=True, extra={'table': endpoints_table})
    raise

def validate_input(body):
    """
    Validate request body

    Args:
        body: Request body dictionary

    Returns:
        tuple: (is_valid, error_message)
    """
    logger.debug("Validating input", extra={'body_keys': list(body.keys())})
    required = ['endpoint_name', 'job_id']
    for field in required:
        if field not in body:
            logger.warning("Missing required field in input", extra={'field': field, 'provided_fields': list(body.keys())})
            return False, f"Missing required field: {field}"
    logger.debug("Input validation passed")
    return True, None

def check_model_exists(s3_path):
    """
    Check if model exists in S3

    Args:
        s3_path: S3 path (s3://bucket/key)

    Returns:
        bool: True if model exists
    """
    logger.debug("Checking if model exists", extra={'s3_path': s3_path})
    try:
        # Parse S3 path
        if not s3_path.startswith('s3://'):
            return False
        
        parts = s3_path[5:].split('/', 1)
        if len(parts) != 2:
            return False
        
        bucket, key = parts
        
        # Check if object exists
        s3.head_object(Bucket=bucket, Key=key)
        logger.debug("Model exists", extra={'s3_path': s3_path})
        return True
    except Exception as e:
        logger.warning("Model does not exist", extra={'s3_path': s3_path, 'error': str(e)})
        return False

def create_ecs_service(endpoint_name, model_s3_path, image):
    """
    Create ECS Fargate service for inference

    Args:
        endpoint_name: Name of the endpoint
        model_s3_path: S3 path to the model
        image: Docker image to use

    Returns:
        dict: Service details including service_arn
    """
    service_logger = get_lambda_logger({'service': 'create_endpoint', 'endpoint_name': endpoint_name})
    
    cluster = os.environ.get('ECS_CLUSTER', 'training-cluster')
    subnet_id = os.environ.get('SUBNET_ID')
    target_group_arn = os.environ.get('TARGET_GROUP_ARN')
    
    service_logger.info(
        "Creating ECS service",
        extra={
            'cluster': cluster,
            'endpoint_name': endpoint_name,
            'subnet_id': subnet_id,
            'target_group_arn': target_group_arn,
            'model_s3_path': model_s3_path
        }
    )
    
    try:
        # Create service configuration
        service_config = {
            'cluster': cluster,
            'serviceName': f'inference-{endpoint_name}',
            'taskDefinition': 'inference-task',
            'desiredCount': 1,
            'launchType': 'FARGATE',
            'networkConfiguration': {
                'awsvpcConfiguration': {
                    'subnets': [subnet_id],
                    'assignPublicIp': 'ENABLED'
                }
            },
            'loadBalancers': [
                {
                    'targetGroupArn': target_group_arn,
                    'containerName': 'inference',
                    'containerPort': 8080
                }
            ]
        }
        
        # Override environment variables for this specific endpoint
        service_config['overrides'] = {
            'containerOverrides': [{
                'name': 'inference',
                'environment': [
                    {'name': 'MODEL_S3_PATH', 'value': model_s3_path},
                    {'name': 'ENDPOINT_NAME', 'value': endpoint_name},
                    {'name': 'AWS_REGION', 'value': region}
                ]
            }]
        }
        
        service_logger.debug("Calling ecs.create_service", extra={'service_name': f'inference-{endpoint_name}'})
        
        response = ecs.create_service(**service_config)
        
        service_logger.debug("ECS create_service response received", extra={'response_keys': list(response.keys())})
        
        if 'service' in response:
            service = response['service']
            service_arn = service.get('serviceArn')
            service_logger.info(
                "ECS service created successfully",
                extra={
                    'service_arn': service_arn,
                    'service_name': service.get('serviceName'),
                    'status': service.get('status')
                }
            )
            return {
                'service_arn': service_arn,
                'service_name': service.get('serviceName'),
                'status': service.get('status')
            }
        else:
            service_logger.error("No service in ECS response")
            return None
        
    except Exception as e:
        service_logger.error("Error creating ECS service", exc_info=True, extra={'error': str(e)})
        return None

def setup_autoscaling(endpoint_name, cluster):
    """
    Configure auto-scaling for the ECS service
    
    Args:
        endpoint_name: Name of the endpoint
        cluster: ECS cluster name
        
    Returns:
        bool: True if successful, False otherwise
    """
    scaling_logger = get_lambda_logger({'service': 'create_endpoint', 'endpoint_name': endpoint_name})
    
    service_name = f'inference-{endpoint_name}'
    resource_id = f'service/{cluster}/{service_name}'
    
    scaling_logger.info("Setting up auto-scaling", extra={
        'endpoint_name': endpoint_name,
        'resource_id': resource_id
    })
    
    try:
        # Step 1: Register scalable target (min=0, max=10)
        scaling_logger.debug("Registering scalable target")
        autoscaling.register_scalable_target(
            ServiceNamespace='ecs',
            ResourceId=resource_id,
            ScalableDimension='ecs:service:DesiredCount',
            MinCapacity=0,  # Scale to zero when idle
            MaxCapacity=10,  # Max 10 tasks
            RoleARN=f'arn:aws:iam::{os.environ.get("AWS_ACCOUNT_ID")}:role/aws-service-role/ecs.application-autoscaling.amazonaws.com/AWSServiceRoleForApplicationAutoScaling_ECSService'
        )
        scaling_logger.info("Scalable target registered", extra={'min': 0, 'max': 10})
        
        # Step 2: Create target tracking scaling policy based on ALB RequestCountPerTarget
        target_group_arn = os.environ.get('TARGET_GROUP_ARN')
        
        # Extract the target group name from ARN for the metric
        # ARN format: arn:aws:elasticloadbalancing:region:account:targetgroup/name/id
        tg_parts = target_group_arn.split(':')
        tg_name_with_id = tg_parts[-1].split('/')  # ['targetgroup', 'name', 'id']
        
        # Get load balancer ARN/name for the full resource label
        alb_arn = os.environ.get('ALB_ARN', '')
        if alb_arn:
            alb_parts = alb_arn.split(':')
            alb_name_with_id = alb_parts[-1].split('/')  # ['app', 'name', 'id']
            # Resource label format: app/lb-name/lb-id/targetgroup/tg-name/tg-id
            resource_label = f"{alb_name_with_id[0]}/{alb_name_with_id[1]}/{alb_name_with_id[2]}/{tg_name_with_id[0]}/{tg_name_with_id[1]}/{tg_name_with_id[2]}"
        else:
            # Fallback: try to construct from target group only
            resource_label = f"targetgroup/{tg_name_with_id[1]}/{tg_name_with_id[2]}"
            scaling_logger.warning("ALB_ARN not set, using simplified resource label")
        
        scaling_logger.debug("Creating scaling policy", extra={'resource_label': resource_label})
        
        autoscaling.put_scaling_policy(
            PolicyName=f'{endpoint_name}-request-count-scaling',
            ServiceNamespace='ecs',
            ResourceId=resource_id,
            ScalableDimension='ecs:service:DesiredCount',
            PolicyType='TargetTrackingScaling',
            TargetTrackingScalingPolicyConfiguration={
                'TargetValue': 100.0,  # Target 100 requests per minute per task
                'PredefinedMetricSpecification': {
                    'PredefinedMetricType': 'ALBRequestCountPerTarget',
                    'ResourceLabel': resource_label
                },
                'ScaleOutCooldown': 60,   # Wait 60 seconds after scaling out
                'ScaleInCooldown': 300,   # Wait 5 minutes before scaling in (conservative)
            }
        )
        
        scaling_logger.info("Auto-scaling policy created successfully", extra={
            'policy_name': f'{endpoint_name}-request-count-scaling',
            'target_value': 100.0,
            'metric': 'ALBRequestCountPerTarget'
        })
        
        return True
        
    except Exception as e:
        scaling_logger.error("Error setting up auto-scaling", exc_info=True, extra={'error': str(e)})
        # Don't fail the entire endpoint creation if auto-scaling setup fails
        # The service will still work, just without auto-scaling
        return False

def lambda_handler(event, context):
    """
    Handle create endpoint request

    Args:
        event: Lambda event
        context: Lambda context

    Returns:
        dict: API Gateway response
    """
    # Extract request ID from context or event
    request_id = getattr(context, 'aws_request_id', None) if context else None
    handler_logger = get_lambda_logger({'service': 'create_endpoint', 'request_id': request_id})
    
    handler_logger.info("Received create endpoint request", extra={'event_keys': list(event.keys())})
    
    try:
        # Parse request
        try:
            body = json.loads(event.get('body', '{}'))
            handler_logger.debug("Parsed request body", extra={'body_keys': list(body.keys())})
        except json.JSONDecodeError as e:
            handler_logger.error("Invalid JSON in request body", exc_info=True)
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                    'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS'
                },
                'body': json.dumps({'error': 'Invalid JSON in request body'})
            }

        # Validate
        valid, error = validate_input(body)
        if not valid:
            handler_logger.warning("Input validation failed", extra={'error': error})
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                    'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS'
                },
                'body': json.dumps({'error': error})
            }

        endpoint_name = body['endpoint_name']
        job_id = body['job_id']
        
        # Check if endpoint already exists
        existing_endpoint = endpoint_store.get_endpoint(endpoint_name)
        if existing_endpoint:
            handler_logger.warning("Endpoint already exists", extra={'endpoint_name': endpoint_name})
            return {
                'statusCode': 409,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                    'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS'
                },
                'body': json.dumps({'error': f'Endpoint {endpoint_name} already exists'})
            }
        
        # Construct model S3 path
        s3_bucket = os.environ.get('S3_BUCKET_NAME', 'ml-platform-bucket')
        model_s3_path = f"s3://{s3_bucket}/models/{job_id}/model.pkl"
        
        # Validate model exists
        if not check_model_exists(model_s3_path):
            handler_logger.warning("Model not found", extra={'model_s3_path': model_s3_path})
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                    'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS'
                },
                'body': json.dumps({'error': f'Model not found at {model_s3_path}'})
            }
        
        # Get inference image
        aws_account_id = os.environ.get('AWS_ACCOUNT_ID', '')
        inference_image = body.get('image', f'{aws_account_id}.dkr.ecr.{region}.amazonaws.com/inference:latest')
        
        # Create endpoint record in DynamoDB
        try:
            endpoint_data = {
                'endpoint_name': endpoint_name,
                'job_id': job_id,
                'model_s3_path': model_s3_path
            }
            endpoint_store.create_endpoint(endpoint_data)
            handler_logger.info("Endpoint record created", extra={'endpoint_name': endpoint_name})
        except Exception as db_error:
            handler_logger.error(
                "Error creating endpoint in DynamoDB",
                exc_info=True,
                extra={'endpoint_name': endpoint_name, 'error': str(db_error)}
            )
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                    'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS'
                },
                'body': json.dumps({
                    'error': 'Database error',
                    'message': str(db_error)
                })
            }

        # Create ECS service
        handler_logger.info("Creating ECS service", extra={'endpoint_name': endpoint_name})
        service_details = create_ecs_service(endpoint_name, model_s3_path, inference_image)
        
        if service_details:
            # Setup auto-scaling for the service
            cluster = os.environ.get('ECS_CLUSTER', 'training-cluster')
            handler_logger.info("Setting up auto-scaling", extra={'endpoint_name': endpoint_name})
            autoscaling_success = setup_autoscaling(endpoint_name, cluster)
            if autoscaling_success:
                handler_logger.info("Auto-scaling configured successfully", extra={'endpoint_name': endpoint_name})
            else:
                handler_logger.warning("Auto-scaling setup failed, endpoint will work without auto-scaling", extra={'endpoint_name': endpoint_name})
            
            # Get ALB DNS name for endpoint URL
            alb_dns = os.environ.get('ALB_DNS_NAME', 'your-alb.amazonaws.com')
            endpoint_url = f"http://{alb_dns}/{endpoint_name}"
            
            # Update endpoint with service details
            endpoint_store.update_endpoint_status(
                endpoint_name,
                'active',
                service_arn=service_details['service_arn'],
                endpoint_url=endpoint_url,
                autoscaling_enabled=autoscaling_success
            )
            
            handler_logger.info("Endpoint created successfully", extra={
                'endpoint_name': endpoint_name,
                'endpoint_url': endpoint_url,
                'autoscaling_enabled': autoscaling_success
            })
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                    'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS'
                },
                'body': json.dumps({
                    'endpoint_name': endpoint_name,
                    'endpoint_url': endpoint_url,
                    'status': 'active',
                    'service_arn': service_details['service_arn']
                })
            }
        else:
            # Service creation failed, update endpoint status
            endpoint_store.update_endpoint_status(endpoint_name, 'failed')
            handler_logger.error("Failed to create ECS service", extra={'endpoint_name': endpoint_name})
            
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                    'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS'
                },
                'body': json.dumps({'error': 'Failed to create ECS service'})
            }

    except Exception as e:
        handler_logger.error("Unexpected error in lambda_handler", exc_info=True, extra={'error': str(e)})
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS'
            },
            'body': json.dumps({'error': str(e)})
        }

