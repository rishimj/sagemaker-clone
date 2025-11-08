import click
import requests
import json
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

load_dotenv()

API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:3000')
logger = get_logger(__name__)

@click.group()
def cli():
    """ML Platform CLI - Submit and manage training jobs"""
    pass

@cli.command()
@click.option('--name', required=True, help='Job name')
@click.option('--image', required=True, help='Docker training image')
@click.option('--data', required=True, help='S3 data path (s3://bucket/path)')
@click.option('--epochs', default=10, type=int, help='Number of epochs')
@click.option('--lr', default=0.001, type=float, help='Learning rate')
def submit(name, image, data, epochs, lr):
    """Submit a training job"""
    submit_logger = get_logger(__name__, {'operation': 'submit', 'job_name': name})
    submit_logger.info("Submitting training job", extra={'job_name': name, 'image': image, 'data': data, 'epochs': epochs, 'lr': lr})
    
    payload = {
        'job_name': name,
        'image': image,
        'input_data': data,
        'hyperparameters': {
            'epochs': epochs,
            'learning_rate': lr
        }
    }

    try:
        submit_logger.debug("Sending POST request", extra={'url': f'{API_BASE_URL}/jobs', 'payload_keys': list(payload.keys())})
        response = requests.post(f'{API_BASE_URL}/jobs', json=payload, timeout=10)
        submit_logger.debug("Received response", extra={'status_code': response.status_code})

        if response.status_code == 200:
            job_id = response.json()['job_id']
            submit_logger.info("Job submitted successfully", extra={'job_id': job_id, 'job_name': name})
            click.echo(click.style(f'✓ Job submitted successfully', fg='green'))
            click.echo(f'Job ID: {job_id}')
        else:
            submit_logger.error("Job submission failed", extra={'status_code': response.status_code, 'response': response.text})
            click.echo(click.style(f'✗ Error: {response.text}', fg='red'))

    except requests.exceptions.Timeout as e:
        submit_logger.error("Request timeout", exc_info=True, extra={'timeout': 10, 'error': str(e)})
        click.echo(click.style(f'✗ Connection timeout: {e}', fg='red'))
    except requests.exceptions.RequestException as e:
        submit_logger.error("Connection error", exc_info=True, extra={'error': str(e), 'url': API_BASE_URL})
        click.echo(click.style(f'✗ Connection error: {e}', fg='red'))
    except Exception as e:
        submit_logger.error("Unexpected error", exc_info=True, extra={'error': str(e)})
        click.echo(click.style(f'✗ Unexpected error: {e}', fg='red'))

@cli.command()
@click.argument('job_id')
def status(job_id):
    """Get job status by ID"""
    status_logger = get_logger(__name__, {'operation': 'status', 'job_id': job_id})
    status_logger.info("Getting job status", extra={'job_id': job_id})
    
    try:
        status_logger.debug("Sending GET request", extra={'url': f'{API_BASE_URL}/jobs/{job_id}'})
        response = requests.get(f'{API_BASE_URL}/jobs/{job_id}', timeout=10)
        status_logger.debug("Received response", extra={'status_code': response.status_code})

        if response.status_code == 200:
            job = response.json()
            status_logger.info("Job status retrieved", extra={'job_id': job_id, 'status': job.get('status')})

            # Pretty print job info
            click.echo(click.style('\n=== Job Status ===', bold=True))
            click.echo(f"Job ID:     {job['job_id']}")
            click.echo(f"Name:       {job.get('job_name', 'N/A')}")

            status_color = {
                'pending': 'yellow',
                'running': 'blue',
                'completed': 'green',
                'failed': 'red'
            }.get(job['status'], 'white')

            click.echo(f"Status:     {click.style(job['status'], fg=status_color)}")
            click.echo(f"Created:    {job.get('created_at', 'N/A')}")

            if 'hyperparameters' in job:
                click.echo(f"Hyperparams: {json.dumps(job['hyperparameters'])}")

            if 's3_output' in job:
                click.echo(f"Output:     {job['s3_output']}")

        elif response.status_code == 404:
            status_logger.warning("Job not found", extra={'job_id': job_id})
            click.echo(click.style(f'✗ Job not found: {job_id}', fg='red'))
        else:
            status_logger.error("Failed to get job status", extra={'status_code': response.status_code, 'response': response.text})
            click.echo(click.style(f'✗ Error: {response.text}', fg='red'))

    except requests.exceptions.Timeout as e:
        status_logger.error("Request timeout", exc_info=True, extra={'timeout': 10, 'error': str(e)})
        click.echo(click.style(f'✗ Connection timeout: {e}', fg='red'))
    except requests.exceptions.RequestException as e:
        status_logger.error("Connection error", exc_info=True, extra={'error': str(e), 'url': API_BASE_URL})
        click.echo(click.style(f'✗ Connection error: {e}', fg='red'))
    except Exception as e:
        status_logger.error("Unexpected error", exc_info=True, extra={'error': str(e)})
        click.echo(click.style(f'✗ Unexpected error: {e}', fg='red'))

@cli.command()
def list():
    """List all jobs (requires list endpoint)"""
    list_logger = get_logger(__name__, {'operation': 'list'})
    list_logger.info("List jobs command called")
    list_logger.warning("List functionality not yet implemented")
    click.echo("List functionality not yet implemented")
    click.echo("You can implement a /jobs GET endpoint to list all jobs")

if __name__ == '__main__':
    cli()

