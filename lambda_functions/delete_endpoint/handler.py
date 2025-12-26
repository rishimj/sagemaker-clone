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
autoscaling = boto3.client('application-autoscaling', region_name=region)

# Initialize logger
logger = get_lambda_logger({'service': 'delete_endpoint', 'region': region})
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

def deregister_autoscaling(endpoint_name, cluster):
    """
    Deregister auto-scaling for the ECS service
    
    Args:
        endpoint_name: Name of the endpoint
        cluster: ECS cluster name
        
    Returns:
        bool: True if successful, False otherwise
    """
    scaling_logger = get_lambda_logger({'service': 'delete_endpoint', 'endpoint_name': endpoint_name})
    
    service_name = f'inference-{endpoint_name}'
    resource_id = f'service/{cluster}/{service_name}'
    
    scaling_logger.info("Deregistering auto-scaling", extra={
        'endpoint_name': endpoint_name,
        'resource_id': resource_id
    })
    
    try:
        # Delete scaling policies first
        scaling_logger.debug("Deleting scaling policies")
        try:
            # Describe policies to get the list
            policies = autoscaling.describe_scaling_policies(
                ServiceNamespace='ecs',
                ResourceId=resource_id,
                ScalableDimension='ecs:service:DesiredCount'
            )
            
            # Delete each policy
            for policy in policies.get('ScalingPolicies', []):
                policy_name = policy['PolicyName']
                scaling_logger.debug(f"Deleting policy: {policy_name}")
                autoscaling.delete_scaling_policy(
                    PolicyName=policy_name,
                    ServiceNamespace='ecs',
                    ResourceId=resource_id,
                    ScalableDimension='ecs:service:DesiredCount'
                )
        except Exception as policy_error:
            scaling_logger.warning("Error deleting policies, continuing", extra={'error': str(policy_error)})
        
        # Deregister scalable target
        scaling_logger.debug("Deregistering scalable target")
        autoscaling.deregister_scalable_target(
            ServiceNamespace='ecs',
            ResourceId=resource_id,
            ScalableDimension='ecs:service:DesiredCount'
        )
        
        scaling_logger.info("Auto-scaling deregistered successfully")
        return True
        
    except Exception as e:
        scaling_logger.error("Error deregistering auto-scaling", exc_info=True, extra={'error': str(e)})
        # Don't fail if deregistration fails - continue with service deletion
        return False

def delete_ecs_service(service_arn, endpoint_name):
    """
    Delete ECS Fargate service

    Args:
        service_arn: ARN of the service to delete
        endpoint_name: Name of the endpoint

    Returns:
        bool: True if successful
    """
    service_logger = get_lambda_logger({'service': 'delete_endpoint', 'endpoint_name': endpoint_name})
    
    cluster = os.environ.get('ECS_CLUSTER', 'training-cluster')
    
    service_logger.info(
        "Deleting ECS service",
        extra={
            'cluster': cluster,
            'service_arn': service_arn,
            'endpoint_name': endpoint_name
        }
    )
    
    try:
        # First, deregister auto-scaling
        service_logger.debug("Deregistering auto-scaling")
        deregister_autoscaling(endpoint_name, cluster)
        
        # Then, scale service to 0 tasks
        service_logger.debug("Scaling service to 0", extra={'service_arn': service_arn})
        ecs.update_service(
            cluster=cluster,
            service=f'inference-{endpoint_name}',
            desiredCount=0
        )
        
        # Finally, delete the service
        service_logger.debug("Deleting service", extra={'service_arn': service_arn})
        response = ecs.delete_service(
            cluster=cluster,
            service=f'inference-{endpoint_name}',
            force=True
        )
        
        service_logger.info(
            "ECS service deleted successfully",
            extra={
                'service_arn': service_arn,
                'endpoint_name': endpoint_name
            }
        )
        return True
        
    except Exception as e:
        service_logger.error("Error deleting ECS service", exc_info=True, extra={'error': str(e), 'service_arn': service_arn})
        return False

def lambda_handler(event, context):
    """
    Handle delete endpoint request

    Args:
        event: Lambda event
        context: Lambda context

    Returns:
        dict: API Gateway response
    """
    # Extract request ID from context or event
    request_id = getattr(context, 'aws_request_id', None) if context else None
    handler_logger = get_lambda_logger({'service': 'delete_endpoint', 'request_id': request_id})
    
    handler_logger.info("Received delete endpoint request", extra={'event_keys': list(event.keys())})
    
    try:
        # Get endpoint name from path parameters
        path_parameters = event.get('pathParameters', {})
        endpoint_name = path_parameters.get('endpoint_name')
        
        if not endpoint_name:
            handler_logger.warning("Missing endpoint_name in path parameters")
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                    'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS'
                },
                'body': json.dumps({'error': 'Missing endpoint_name in path'})
            }
        
        handler_logger.debug("Parsed endpoint name", extra={'endpoint_name': endpoint_name})
        
        # Get endpoint from database
        endpoint = endpoint_store.get_endpoint(endpoint_name)
        if not endpoint:
            handler_logger.warning("Endpoint not found", extra={'endpoint_name': endpoint_name})
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                    'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS'
                },
                'body': json.dumps({'error': f'Endpoint {endpoint_name} not found'})
            }
        
        # Delete ECS service if it exists
        service_arn = endpoint.get('service_arn')
        if service_arn:
            handler_logger.info("Deleting ECS service", extra={'endpoint_name': endpoint_name, 'service_arn': service_arn})
            delete_success = delete_ecs_service(service_arn, endpoint_name)
            if not delete_success:
                handler_logger.warning("Failed to delete ECS service, continuing with database deletion", extra={'endpoint_name': endpoint_name})
        else:
            handler_logger.debug("No service ARN found, skipping ECS deletion", extra={'endpoint_name': endpoint_name})
        
        # Delete from database
        try:
            endpoint_store.delete_endpoint(endpoint_name)
            handler_logger.info("Endpoint deleted successfully", extra={'endpoint_name': endpoint_name})
        except Exception as db_error:
            handler_logger.error(
                "Error deleting endpoint from DynamoDB",
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
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS'
            },
            'body': json.dumps({
                'message': f'Endpoint {endpoint_name} deleted successfully',
                'endpoint_name': endpoint_name
            })
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

