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

class S3Handler:
    """Handle S3 operations for ML platform"""

    def __init__(self, bucket_name, client=None):
        """
        Initialize S3 handler

        Args:
            bucket_name: Name of S3 bucket
            client: Optional boto3 S3 client (for testing)
        """
        import boto3
        self.bucket_name = bucket_name
        self.client = client or boto3.client('s3')
        self.logger = get_logger(__name__, {'bucket': bucket_name})
        self.logger.debug("S3Handler initialized", extra={'bucket_name': bucket_name})

    def upload_file(self, local_path, s3_key):
        """
        Upload file to S3

        Args:
            local_path: Local file path
            s3_key: S3 object key

        Returns:
            bool: True if successful, False otherwise
        """
        self.logger.info("Uploading file to S3", extra={'local_path': local_path, 's3_key': s3_key, 'bucket': self.bucket_name})
        try:
            self.client.upload_file(local_path, self.bucket_name, s3_key)
            self.logger.info("File uploaded successfully", extra={'s3_key': s3_key, 'bucket': self.bucket_name})
            return True
        except Exception as e:
            self.logger.error(
                "Error uploading file to S3",
                exc_info=True,
                extra={'local_path': local_path, 's3_key': s3_key, 'bucket': self.bucket_name, 'error': str(e)}
            )
            return False

    def download_file(self, s3_key, local_path):
        """
        Download file from S3

        Args:
            s3_key: S3 object key
            local_path: Local file path to save

        Returns:
            bool: True if successful, False otherwise
        """
        self.logger.info("Downloading file from S3", extra={'s3_key': s3_key, 'local_path': local_path, 'bucket': self.bucket_name})
        try:
            self.client.download_file(self.bucket_name, s3_key, local_path)
            self.logger.info("File downloaded successfully", extra={'s3_key': s3_key, 'local_path': local_path})
            return True
        except Exception as e:
            self.logger.error(
                "Error downloading file from S3",
                exc_info=True,
                extra={'s3_key': s3_key, 'local_path': local_path, 'bucket': self.bucket_name, 'error': str(e)}
            )
            return False

    def file_exists(self, s3_key):
        """
        Check if file exists in S3

        Args:
            s3_key: S3 object key

        Returns:
            bool: True if exists, False otherwise
        """
        self.logger.debug("Checking if file exists in S3", extra={'s3_key': s3_key, 'bucket': self.bucket_name})
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=s3_key)
            self.logger.debug("File exists in S3", extra={'s3_key': s3_key})
            return True
        except Exception as e:
            self.logger.debug("File does not exist in S3", extra={'s3_key': s3_key, 'error': str(e)})
            return False

    def list_files(self, prefix=''):
        """
        List files in S3 with given prefix

        Args:
            prefix: S3 key prefix to filter

        Returns:
            list: List of S3 keys
        """
        self.logger.debug("Listing files in S3", extra={'prefix': prefix, 'bucket': self.bucket_name})
        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            if 'Contents' not in response:
                self.logger.debug("No files found", extra={'prefix': prefix})
                return []
            files = [obj['Key'] for obj in response['Contents']]
            self.logger.info("Files listed successfully", extra={'prefix': prefix, 'count': len(files)})
            return files
        except Exception as e:
            self.logger.error(
                "Error listing files in S3",
                exc_info=True,
                extra={'prefix': prefix, 'bucket': self.bucket_name, 'error': str(e)}
            )
            raise