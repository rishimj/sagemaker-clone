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
    from storage.job_store import JobStore
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
logger = get_lambda_logger({'service': 'get_job_status', 'region': region})
logger.info("Initialized DynamoDB client", extra={'region': region})

dynamodb_table = os.environ.get('DYNAMODB_TABLE', 'ml-jobs')
logger.info("Initializing JobStore", extra={'table': dynamodb_table})

try:
    job_store = JobStore(dynamodb_table, dynamodb)
    logger.info("JobStore initialized successfully", extra={'table_name': job_store.table.table_name})
except Exception as e:
    logger.error("Failed to initialize JobStore", exc_info=True, extra={'table': dynamodb_table})
    raise

def lambda_handler(event, context):
    """
    Get job status

    Args:
        event: Lambda event with pathParameters
        context: Lambda context

    Returns:
        dict: API Gateway response
    """
    # Extract request ID from context
    request_id = getattr(context, 'aws_request_id', None) if context else None
    handler_logger = get_lambda_logger({'service': 'get_job_status', 'request_id': request_id})
    
    handler_logger.info("Received get job status request", extra={'event_keys': list(event.keys())})
    
    try:
        # Get job_id from path parameters
        if 'pathParameters' not in event or not event['pathParameters']:
            handler_logger.warning("Missing pathParameters in event")
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                },
                'body': json.dumps({'error': 'Missing job_id parameter'})
            }
        
        if 'job_id' not in event['pathParameters']:
            handler_logger.warning("Missing job_id in pathParameters", extra={'path_params': event.get('pathParameters', {})})
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                },
                'body': json.dumps({'error': 'Missing job_id parameter'})
            }

        job_id = event['pathParameters']['job_id']
        handler_logger.info("Retrieving job status", extra={'job_id': job_id})

        # Get job from database
        try:
            job = job_store.get_job(job_id)
        except Exception as db_error:
            handler_logger.error(
                "Error retrieving job from DynamoDB",
                exc_info=True,
                extra={'job_id': job_id, 'table': dynamodb_table, 'error': str(db_error)}
            )
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                },
                'body': json.dumps({'error': 'Database error', 'message': str(db_error)})
            }

        if not job:
            handler_logger.warning("Job not found", extra={'job_id': job_id})
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                },
                'body': json.dumps({'error': 'Job not found'})
            }

        handler_logger.info(
            "Job retrieved successfully",
            extra={
                'job_id': job_id,
                'status': job.get('status'),
                'job_name': job.get('job_name')
            }
        )

        # Return job data
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
            },
            'body': json.dumps(job, default=str)
        }

    except Exception as e:
        handler_logger.error("Unexpected error in lambda_handler", exc_info=True, extra={'error': str(e)})
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
            },
            'body': json.dumps({'error': str(e)})
        }