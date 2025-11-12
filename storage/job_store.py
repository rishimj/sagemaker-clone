import uuid
import time
from decimal import Decimal

try:
    from storage.logger import get_logger
except ImportError:
    # Fallback if logger not available
    import logging
    def get_logger(name, context=None):
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

logger = get_logger(__name__)

class JobStore:
    """Handle DynamoDB operations for job tracking"""

    def __init__(self, table_name, dynamodb_resource=None):
        """
        Initialize job store

        Args:
            table_name: DynamoDB table name
            dynamodb_resource: Optional boto3 DynamoDB resource (for testing)
        """
        import boto3
        self.dynamodb = dynamodb_resource or boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        self.logger = get_logger(__name__, {'table': table_name})
        self.logger.debug("JobStore initialized", extra={'table_name': table_name})
    
    def _convert_floats_to_decimals(self, obj):
        """
        Recursively convert floats to Decimals for DynamoDB compatibility
        """
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: self._convert_floats_to_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_floats_to_decimals(item) for item in obj]
        else:
            return obj

    def create_job(self, job_data):
        """
        Create new job entry

        Args:
            job_data: Dictionary of job parameters

        Returns:
            str: Job ID if successful, None otherwise
        """
        job_id = f"job-{uuid.uuid4().hex[:8]}"
        job_logger = get_logger(__name__, {'job_id': job_id, 'table': self.table.table_name})

        item = {
            'job_id': job_id,
            'status': 'pending',
            'created_at': int(time.time()),
            **job_data
        }
        
        job_logger.debug("Creating job", extra={'job_name': job_data.get('job_name'), 'item_keys': list(item.keys())})
        
        # Convert floats to Decimals for DynamoDB compatibility
        item = self._convert_floats_to_decimals(item)

        try:
            self.table.put_item(Item=item)
            job_logger.info("Job created successfully", extra={'job_id': job_id, 'job_name': job_data.get('job_name')})
            return job_id
        except Exception as e:
            job_logger.error(
                "Error creating job in DynamoDB",
                exc_info=True,
                extra={
                    'job_id': job_id,
                    'table_name': self.table.table_name,
                    'item_keys': list(item.keys()),
                    'error': str(e)
                }
            )
            # Re-raise to get better error information
            raise Exception(f"DynamoDB error: {str(e)}") from e

    def get_job(self, job_id):
        """
        Get job by ID

        Args:
            job_id: Job identifier

        Returns:
            dict: Job data if found, None otherwise
        """
        job_logger = get_logger(__name__, {'job_id': job_id, 'table': self.table.table_name})
        job_logger.debug("Retrieving job", extra={'job_id': job_id})
        
        try:
            response = self.table.get_item(Key={'job_id': job_id})
            item = response.get('Item')
            if item:
                job_logger.debug("Job retrieved successfully", extra={'job_id': job_id, 'status': item.get('status')})
            else:
                job_logger.debug("Job not found", extra={'job_id': job_id})
            return item
        except Exception as e:
            job_logger.error(
                "Error getting job from DynamoDB",
                exc_info=True,
                extra={'job_id': job_id, 'error': str(e)}
            )
            raise

    def update_job_status(self, job_id, status, **kwargs):
        """
        Update job status and optional additional fields

        Args:
            job_id: Job identifier
            status: New status value
            **kwargs: Additional fields to update

        Returns:
            bool: True if successful, False otherwise
        """
        job_logger = get_logger(__name__, {'job_id': job_id, 'table': self.table.table_name})
        job_logger.debug(
            "Updating job status",
            extra={'job_id': job_id, 'status': status, 'additional_fields': list(kwargs.keys())}
        )
        
        try:
            # Build update expression
            update_expr = 'SET #s = :status'
            expr_values = {':status': status}
            expr_names = {'#s': 'status'}

            # Add optional fields
            for key, value in kwargs.items():
                update_expr += f', {key} = :{key}'
                expr_values[f':{key}'] = value

            self.table.update_item(
                Key={'job_id': job_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values
            )
            job_logger.info(
                "Job status updated successfully",
                extra={'job_id': job_id, 'status': status, 'additional_fields': list(kwargs.keys())}
            )
            return True
        except Exception as e:
            job_logger.error(
                "Error updating job status",
                exc_info=True,
                extra={'job_id': job_id, 'status': status, 'error': str(e)}
            )
            return False

    def list_jobs(self, limit=100):
        """
        List all jobs

        Args:
            limit: Maximum number of jobs to return

        Returns:
            list: List of job dictionaries
        """
        list_logger = get_logger(__name__, {'table': self.table.table_name})
        list_logger.debug("Listing jobs", extra={'limit': limit})
        
        try:
            response = self.table.scan(Limit=limit)
            items = response.get('Items', [])
            list_logger.info("Jobs listed successfully", extra={'count': len(items), 'limit': limit})
            return items
        except Exception as e:
            list_logger.error(
                "Error listing jobs",
                exc_info=True,
                extra={'limit': limit, 'error': str(e)}
            )
            raise