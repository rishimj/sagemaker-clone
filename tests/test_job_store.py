import pytest
import time
from storage.job_store import JobStore

@pytest.fixture
def job_table(dynamodb_resource):
    """Create test DynamoDB table"""
    table = dynamodb_resource.create_table(
        TableName='test-jobs',
        KeySchema=[{'AttributeName': 'job_id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'job_id', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST'
    )
    return table

def test_create_job(dynamodb_resource, job_table):
    """Test creating a new job"""
    store = JobStore('test-jobs', dynamodb_resource)

    job_data = {
        'job_name': 'test-job',
        'image': 'training:latest',
        's3_input': 's3://bucket/data',
        's3_output': 's3://bucket/output',
        'hyperparameters': {'epochs': 10}
    }

    job_id = store.create_job(job_data)

    assert job_id is not None
    assert job_id.startswith('job-')
    assert len(job_id) > 8

def test_get_job(dynamodb_resource, job_table):
    """Test retrieving a job"""
    store = JobStore('test-jobs', dynamodb_resource)

    # Create job
    job_data = {'job_name': 'test', 'status': 'pending'}
    job_id = store.create_job(job_data)

    # Get job
    job = store.get_job(job_id)

    assert job is not None
    assert job['job_id'] == job_id
    assert job['status'] == 'pending'
    assert 'created_at' in job

def test_update_job_status(dynamodb_resource, job_table):
    """Test updating job status"""
    store = JobStore('test-jobs', dynamodb_resource)

    job_id = store.create_job({'job_name': 'test', 'status': 'pending'})

    result = store.update_job_status(job_id, 'running')

    assert result is True
    job = store.get_job(job_id)
    assert job['status'] == 'running'

def test_update_job_with_additional_fields(dynamodb_resource, job_table):
    """Test updating job with extra fields"""
    store = JobStore('test-jobs', dynamodb_resource)

    job_id = store.create_job({'job_name': 'test'})

    store.update_job_status(job_id, 'running', task_arn='arn:aws:ecs:task/123')

    job = store.get_job(job_id)
    assert job['status'] == 'running'
    assert job['task_arn'] == 'arn:aws:ecs:task/123'

def test_list_jobs(dynamodb_resource, job_table):
    """Test listing all jobs"""
    store = JobStore('test-jobs', dynamodb_resource)

    # Create multiple jobs
    store.create_job({'job_name': 'job1'})
    store.create_job({'job_name': 'job2'})
    store.create_job({'job_name': 'job3'})

    jobs = store.list_jobs()

    assert len(jobs) == 3
    job_names = [job['job_name'] for job in jobs]
    assert 'job1' in job_names
    assert 'job2' in job_names
    assert 'job3' in job_names

def test_job_not_found(dynamodb_resource, job_table):
    """Test getting non-existent job"""
    store = JobStore('test-jobs', dynamodb_resource)

    job = store.get_job('non-existent-id')

    assert job is None

def test_create_job_sets_default_status(dynamodb_resource, job_table):
    """Test that new jobs default to pending status"""
    store = JobStore('test-jobs', dynamodb_resource)

    job_id = store.create_job({'job_name': 'test'})
    job = store.get_job(job_id)

    assert job['status'] == 'pending'

def test_create_job_sets_timestamp(dynamodb_resource, job_table):
    """Test that new jobs have created_at timestamp"""
    store = JobStore('test-jobs', dynamodb_resource)

    before = int(time.time())
    job_id = store.create_job({'job_name': 'test'})
    after = int(time.time())

    job = store.get_job(job_id)

    assert 'created_at' in job
    assert before <= job['created_at'] <= after