import pytest
import os
from storage.s3_handler import S3Handler

def test_upload_file(s3_client):
    """Test uploading a file to S3"""
    # Setup
    bucket_name = 'test-bucket'
    s3_client.create_bucket(Bucket=bucket_name)
    handler = S3Handler(bucket_name, s3_client)

    # Create temp file
    test_file = '/tmp/test.txt'
    with open(test_file, 'w') as f:
        f.write('test data')

    # Test
    result = handler.upload_file(test_file, 'data/test.txt')

    # Assert
    assert result is True
    assert handler.file_exists('data/test.txt')

def test_download_file(s3_client):
    """Test downloading a file from S3"""
    # Setup
    bucket_name = 'test-bucket'
    s3_client.create_bucket(Bucket=bucket_name)
    s3_client.put_object(Bucket=bucket_name, Key='data/test.txt', Body=b'test data')
    handler = S3Handler(bucket_name, s3_client)

    # Test
    result = handler.download_file('data/test.txt', '/tmp/downloaded.txt')

    # Assert
    assert result is True
    with open('/tmp/downloaded.txt', 'r') as f:
        assert f.read() == 'test data'

def test_file_exists(s3_client):
    """Test checking if file exists"""
    bucket_name = 'test-bucket'
    s3_client.create_bucket(Bucket=bucket_name)
    s3_client.put_object(Bucket=bucket_name, Key='exists.txt', Body=b'data')
    handler = S3Handler(bucket_name, s3_client)

    assert handler.file_exists('exists.txt') is True
    assert handler.file_exists('not-exists.txt') is False

def test_list_files(s3_client):
    """Test listing files with prefix"""
    bucket_name = 'test-bucket'
    s3_client.create_bucket(Bucket=bucket_name)
    s3_client.put_object(Bucket=bucket_name, Key='models/model1.pth', Body=b'')
    s3_client.put_object(Bucket=bucket_name, Key='models/model2.pth', Body=b'')
    handler = S3Handler(bucket_name, s3_client)

    files = handler.list_files('models/')
    assert len(files) == 2
    assert 'models/model1.pth' in files
    assert 'models/model2.pth' in files

def test_upload_nonexistent_file(s3_client):
    """Test uploading a file that doesn't exist"""
    bucket_name = 'test-bucket'
    s3_client.create_bucket(Bucket=bucket_name)
    handler = S3Handler(bucket_name, s3_client)

    result = handler.upload_file('/tmp/nonexistent.txt', 'data/test.txt')

    assert result is False

def test_download_nonexistent_file(s3_client):
    """Test downloading a file that doesn't exist"""
    bucket_name = 'test-bucket'
    s3_client.create_bucket(Bucket=bucket_name)
    handler = S3Handler(bucket_name, s3_client)

    result = handler.download_file('nonexistent.txt', '/tmp/download.txt')

    assert result is False