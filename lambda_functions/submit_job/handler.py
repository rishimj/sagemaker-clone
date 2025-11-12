import boto3
import json
import os
import sys
import traceback

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
ecs = boto3.client('ecs', region_name=region)

# Initialize logger
logger = get_lambda_logger({'service': 'submit_job', 'region': region})
logger.info("Initialized boto3 clients", extra={'region': region})

# Initialize job store with environment variable
dynamodb_table = os.environ.get('DYNAMODB_TABLE', 'ml-jobs')
logger.info("Initializing JobStore", extra={'table': dynamodb_table})

try:
    job_store = JobStore(dynamodb_table, dynamodb)
    logger.info("JobStore initialized successfully", extra={'table_name': job_store.table.table_name})
except Exception as e:
    logger.error("Failed to initialize JobStore", exc_info=True, extra={'table': dynamodb_table})
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
    required = ['job_name', 'image', 'input_data']
    for field in required:
        if field not in body:
            logger.warning("Missing required field in input", extra={'field': field, 'provided_fields': list(body.keys())})
            return False, f"Missing required field: {field}"
    logger.debug("Input validation passed")
    return True, None

def start_ecs_task(job_id, image, s3_input, s3_output, hyperparams):
    """
    Start ECS Fargate task

    Args:
        job_id: Job identifier
        image: Docker image to run
        s3_input: S3 input data path
        s3_output: S3 output path
        hyperparams: Hyperparameters dictionary

    Returns:
        str: Task ARN if successful, None otherwise
    """
    task_logger = get_lambda_logger({'service': 'submit_job', 'job_id': job_id})
    cluster = os.environ.get('ECS_CLUSTER', 'training-cluster')
    subnet_id = os.environ.get('SUBNET_ID')
    
    task_logger.info(
        "Starting ECS task",
        extra={
            'cluster': cluster,
            'task_definition': 'training-job',
            'subnet_id': subnet_id,
            'image': image,
            's3_input': s3_input,
            's3_output': s3_output,
            'hyperparams': hyperparams
        }
    )
    
    try:
        task_config = {
            'cluster': cluster,
            'taskDefinition': 'training-job',
            'launchType': 'FARGATE',
            'networkConfiguration': {
                'awsvpcConfiguration': {
                    'subnets': [subnet_id],
                    'assignPublicIp': 'ENABLED'
                }
            },
            'overrides': {
                'containerOverrides': [{
                    'name': 'training',
                    # Note: ECS Fargate does NOT support image override in containerOverrides
                    # The image must be specified in the task definition
                    # For now, we use the image from task definition and pass it as env var
                    'environment': [
                        {'name': 'JOB_ID', 'value': job_id},
                        {'name': 'S3_INPUT', 'value': s3_input},
                        {'name': 'S3_OUTPUT', 'value': s3_output},
                        {'name': 'HYPERPARAMS', 'value': json.dumps(hyperparams)},
                        {'name': 'IMAGE_URI', 'value': image},  # Pass image URI as env var for reference
                        {'name': 'DYNAMODB_TABLE', 'value': os.environ.get('DYNAMODB_TABLE', 'ml-jobs')},
                        {'name': 'AWS_REGION', 'value': region}
                    ]
                }]
            }
        }
        
        task_logger.debug("Calling ecs.run_task", extra={'task_config_keys': list(task_config.keys())})
        
        response = ecs.run_task(**task_config)
        
        task_logger.debug("ECS run_task response received", extra={'response_keys': list(response.keys())})
        
        if 'tasks' in response and response['tasks']:
            task = response['tasks'][0]
            task_arn = task.get('taskArn')
            task_logger.info(
                "ECS task started successfully",
                extra={
                    'task_arn': task_arn,
                    'task_status': task.get('lastStatus'),
                    'desired_status': task.get('desiredStatus')
                }
            )
            return task_arn
        else:
            task_logger.warning("No tasks in ECS response")
        
        if 'failures' in response and response['failures']:
            for failure in response['failures']:
                task_logger.error(
                    "ECS task failure",
                    extra={
                        'arn': failure.get('arn'),
                        'reason': failure.get('reason'),
                        'detail': failure.get('detail')
                    }
                )
            return None
        
        task_logger.error("Unexpected ECS response format", extra={'response_keys': list(response.keys())})
        return None
        
    except Exception as e:
        task_logger.error("Error starting ECS task", exc_info=True, extra={'error': str(e)})
        return None

def lambda_handler(event, context):
    """
    Handle job submission request

    Args:
        event: Lambda event
        context: Lambda context

    Returns:
        dict: API Gateway response
    """
    # Extract request ID from context or event
    request_id = getattr(context, 'aws_request_id', None) if context else None
    handler_logger = get_lambda_logger({'service': 'submit_job', 'request_id': request_id})
    
    handler_logger.info("Received job submission request", extra={'event_keys': list(event.keys())})
    
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
                    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
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
                    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                },
                'body': json.dumps({'error': error})
            }

        # Prepare job data
        job_data = {
            'job_name': body['job_name'],
            'image': body['image'],
            's3_input': body['input_data'],
            's3_output': f"s3://{os.environ.get('S3_BUCKET_NAME', 'ml-platform-bucket')}/models/{body['job_name']}",
            'hyperparameters': body.get('hyperparameters', {})
        }
        
        handler_logger.info("Prepared job data", extra={'job_name': job_data['job_name'], 's3_output': job_data['s3_output']})

        # Create job in DB
        try:
            job_id = job_store.create_job(job_data)
            if not job_id:
                handler_logger.error("Job creation returned None")
                return {
                    'statusCode': 500,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                    },
                    'body': json.dumps({'error': 'Failed to create job - create_job returned None'})
                }
            handler_logger.info("Job created successfully", extra={'job_id': job_id})
        except Exception as db_error:
            handler_logger.error(
                "Error creating job in DynamoDB",
                exc_info=True,
                extra={'table': dynamodb_table, 'error': str(db_error)}
            )
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                },
                'body': json.dumps({
                    'error': 'Database error',
                    'message': str(db_error),
                    'table': dynamodb_table
                })
            }

        # Start ECS task
        handler_logger.info("Attempting to start ECS task", extra={'job_id': job_id})
        task_arn = start_ecs_task(
            job_id,
            body['image'],
            body['input_data'],
            job_data['s3_output'],
            job_data['hyperparameters']
        )

        # Update job with task ARN if successful
        if task_arn:
            handler_logger.info("ECS task started successfully", extra={'job_id': job_id, 'task_arn': task_arn})
            try:
                update_result = job_store.update_job_status(job_id, 'running', task_arn=task_arn)
                if update_result:
                    handler_logger.info("Job status updated to 'running'", extra={'job_id': job_id, 'task_arn': task_arn})
                else:
                    handler_logger.warning("Failed to update job status", extra={'job_id': job_id})
            except Exception as update_error:
                handler_logger.error("Error updating job status", exc_info=True, extra={'job_id': job_id, 'error': str(update_error)})
        else:
            handler_logger.warning("ECS task failed to start", extra={'job_id': job_id})
            # Keep job status as 'pending' if task fails to start

        handler_logger.info("Job submission completed", extra={'job_id': job_id, 'status': 'success'})
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
            },
            'body': json.dumps({'job_id': job_id})
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