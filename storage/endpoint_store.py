"""
Endpoint Store - Manages model endpoint records in DynamoDB
"""
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

class EndpointStore:
    """Handle DynamoDB operations for endpoint tracking"""

    def __init__(self, table_name, dynamodb_resource=None):
        """
        Initialize endpoint store

        Args:
            table_name: DynamoDB table name
            dynamodb_resource: Optional boto3 DynamoDB resource (for testing)
        """
        import boto3
        self.dynamodb = dynamodb_resource or boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        self.logger = get_logger(__name__, {'table': table_name})
        self.logger.debug("EndpointStore initialized", extra={'table_name': table_name})
    
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

    def create_endpoint(self, endpoint_data):
        """
        Create new endpoint entry

        Args:
            endpoint_data: Dictionary with endpoint parameters
                Required: endpoint_name, job_id, model_s3_path
                Optional: service_arn, endpoint_url

        Returns:
            str: Endpoint name if successful, None otherwise
        """
        endpoint_name = endpoint_data.get('endpoint_name')
        if not endpoint_name:
            raise ValueError("endpoint_name is required")
        
        endpoint_logger = get_logger(__name__, {'endpoint_name': endpoint_name, 'table': self.table.table_name})

        item = {
            'endpoint_name': endpoint_name,
            'status': 'creating',
            'created_at': int(time.time()),
            'job_id': endpoint_data.get('job_id', ''),
            'model_s3_path': endpoint_data.get('model_s3_path', ''),
            'service_arn': endpoint_data.get('service_arn', ''),
            'endpoint_url': endpoint_data.get('endpoint_url', ''),
            'task_definition': endpoint_data.get('task_definition', ''),
            'target_group_arn': endpoint_data.get('target_group_arn', '')
        }
        
        endpoint_logger.debug("Creating endpoint", extra={'endpoint_name': endpoint_name, 'item_keys': list(item.keys())})
        
        # Convert floats to Decimals for DynamoDB compatibility
        item = self._convert_floats_to_decimals(item)

        try:
            self.table.put_item(Item=item)
            endpoint_logger.info("Endpoint created successfully", extra={'endpoint_name': endpoint_name})
            return endpoint_name
        except Exception as e:
            endpoint_logger.error(
                "Error creating endpoint in DynamoDB",
                exc_info=True,
                extra={
                    'endpoint_name': endpoint_name,
                    'table_name': self.table.table_name,
                    'item_keys': list(item.keys()),
                    'error': str(e)
                }
            )
            raise Exception(f"DynamoDB error: {str(e)}") from e

    def get_endpoint(self, endpoint_name):
        """
        Get endpoint by name

        Args:
            endpoint_name: Endpoint identifier

        Returns:
            dict: Endpoint data if found, None otherwise
        """
        endpoint_logger = get_logger(__name__, {'endpoint_name': endpoint_name, 'table': self.table.table_name})
        endpoint_logger.debug("Retrieving endpoint", extra={'endpoint_name': endpoint_name})
        
        try:
            response = self.table.get_item(Key={'endpoint_name': endpoint_name})
            item = response.get('Item')
            if item:
                endpoint_logger.debug("Endpoint retrieved successfully", extra={'endpoint_name': endpoint_name, 'status': item.get('status')})
            else:
                endpoint_logger.debug("Endpoint not found", extra={'endpoint_name': endpoint_name})
            return item
        except Exception as e:
            endpoint_logger.error(
                "Error getting endpoint from DynamoDB",
                exc_info=True,
                extra={'endpoint_name': endpoint_name, 'error': str(e)}
            )
            raise

    def update_endpoint_status(self, endpoint_name, status, **kwargs):
        """
        Update endpoint status and optional additional fields

        Args:
            endpoint_name: Endpoint identifier
            status: New status value
            **kwargs: Additional fields to update

        Returns:
            bool: True if successful, False otherwise
        """
        endpoint_logger = get_logger(__name__, {'endpoint_name': endpoint_name, 'table': self.table.table_name})
        endpoint_logger.debug(
            "Updating endpoint status",
            extra={'endpoint_name': endpoint_name, 'status': status, 'additional_fields': list(kwargs.keys())}
        )
        
        try:
            # Build update expression
            update_expr = 'SET #s = :status'
            expr_values = {':status': status}
            expr_names = {'#s': 'status'}

            # Add optional fields
            for key, value in kwargs.items():
                # Convert floats to Decimals
                value = self._convert_floats_to_decimals(value)
                update_expr += f', {key} = :{key}'
                expr_values[f':{key}'] = value

            self.table.update_item(
                Key={'endpoint_name': endpoint_name},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values
            )
            endpoint_logger.info(
                "Endpoint status updated successfully",
                extra={'endpoint_name': endpoint_name, 'status': status, 'additional_fields': list(kwargs.keys())}
            )
            return True
        except Exception as e:
            endpoint_logger.error(
                "Error updating endpoint status",
                exc_info=True,
                extra={'endpoint_name': endpoint_name, 'status': status, 'error': str(e)}
            )
            return False

    def list_endpoints(self, limit=100):
        """
        List all endpoints

        Args:
            limit: Maximum number of endpoints to return

        Returns:
            list: List of endpoint dictionaries
        """
        list_logger = get_logger(__name__, {'table': self.table.table_name})
        list_logger.debug("Listing endpoints", extra={'limit': limit})
        
        try:
            response = self.table.scan(Limit=limit)
            items = response.get('Items', [])
            list_logger.info("Endpoints listed successfully", extra={'count': len(items), 'limit': limit})
            return items
        except Exception as e:
            list_logger.error(
                "Error listing endpoints",
                exc_info=True,
                extra={'limit': limit, 'error': str(e)}
            )
            raise

    def delete_endpoint(self, endpoint_name):
        """
        Delete endpoint from database

        Args:
            endpoint_name: Endpoint identifier

        Returns:
            bool: True if successful, False otherwise
        """
        endpoint_logger = get_logger(__name__, {'endpoint_name': endpoint_name, 'table': self.table.table_name})
        endpoint_logger.debug("Deleting endpoint", extra={'endpoint_name': endpoint_name})
        
        try:
            self.table.delete_item(Key={'endpoint_name': endpoint_name})
            endpoint_logger.info("Endpoint deleted successfully", extra={'endpoint_name': endpoint_name})
            return True
        except Exception as e:
            endpoint_logger.error(
                "Error deleting endpoint",
                exc_info=True,
                extra={'endpoint_name': endpoint_name, 'error': str(e)}
            )
            return False

