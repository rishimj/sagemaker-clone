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

# Initialize logger
logger = get_lambda_logger({'service': 'get_endpoint_status', 'region': region})
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

def lambda_handler(event, context):
    """
    Handle get endpoint status request

    Args:
        event: Lambda event
        context: Lambda context

    Returns:
        dict: API Gateway response
    """
    # Extract request ID from context or event
    request_id = getattr(context, 'aws_request_id', None) if context else None
    handler_logger = get_lambda_logger({'service': 'get_endpoint_status', 'request_id': request_id})
    
    handler_logger.info("Received get endpoint status request", extra={'event_keys': list(event.keys())})
    
    try:
        # Get endpoint name from path parameters
        path_parameters = event.get('pathParameters', {})
        endpoint_name = path_parameters.get('endpoint_name')
        
        # If no specific endpoint name, list all endpoints
        if not endpoint_name:
            handler_logger.debug("No endpoint_name provided, listing all endpoints")
            try:
                endpoints = endpoint_store.list_endpoints()
                handler_logger.info("Listed endpoints successfully", extra={'count': len(endpoints)})
                
                # Convert Decimal to float for JSON serialization
                def convert_decimals(obj):
                    if isinstance(obj, list):
                        return [convert_decimals(item) for item in obj]
                    elif isinstance(obj, dict):
                        return {k: convert_decimals(v) for k, v in obj.items()}
                    elif hasattr(obj, '__float__'):
                        return float(obj)
                    return obj
                
                endpoints = convert_decimals(endpoints)
                
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                        'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS'
                    },
                    'body': json.dumps({
                        'endpoints': endpoints,
                        'count': len(endpoints)
                    })
                }
            except Exception as list_error:
                handler_logger.error("Error listing endpoints", exc_info=True, extra={'error': str(list_error)})
                return {
                    'statusCode': 500,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                        'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS'
                    },
                    'body': json.dumps({'error': str(list_error)})
                }
        
        handler_logger.debug("Parsed endpoint name", extra={'endpoint_name': endpoint_name})
        
        # Get specific endpoint from database
        try:
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
            
            handler_logger.info("Retrieved endpoint successfully", extra={'endpoint_name': endpoint_name, 'status': endpoint.get('status')})
            
            # Convert Decimal to float for JSON serialization
            def convert_decimals(obj):
                if isinstance(obj, dict):
                    return {k: convert_decimals(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_decimals(item) for item in obj]
                elif hasattr(obj, '__float__'):
                    return float(obj)
                return obj
            
            endpoint = convert_decimals(endpoint)
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                    'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS'
                },
                'body': json.dumps(endpoint)
            }
            
        except Exception as db_error:
            handler_logger.error(
                "Error getting endpoint from DynamoDB",
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

