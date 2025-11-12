"""
Simple Flask server for ML Platform UI
Allows users to upload datasets and download trained models
"""
import os
import boto3
import requests
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# Configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
AWS_ACCOUNT_ID = os.getenv('AWS_ACCOUNT_ID', 'YOUR_ACCOUNT_ID')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'your-ml-platform-bucket')
API_BASE_URL = os.getenv('API_BASE_URL', 'https://your-api-id.execute-api.us-east-1.amazonaws.com/prod')
TRAINING_IMAGE = os.getenv('TRAINING_IMAGE', f'{AWS_ACCOUNT_ID}.dkr.ecr.{AWS_REGION}.amazonaws.com/training:latest')

# Initialize AWS clients
s3_client = boto3.client('s3', region_name=AWS_REGION)

@app.route('/')
def index():
    """Serve the main UI page"""
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_dataset():
    """Upload dataset to S3 and return S3 path"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Get job name from form data or generate one
        job_name = request.form.get('job_name', secure_filename(file.filename).rsplit('.', 1)[0])
        
        # Secure the filename
        filename = secure_filename(file.filename)
        timestamp = str(int(os.urandom(4).hex(), 16))
        s3_key = f"datasets/{job_name}_{timestamp}/{filename}"
        
        # Upload to S3
        try:
            s3_client.upload_fileobj(file, S3_BUCKET_NAME, s3_key)
            s3_path = f"s3://{S3_BUCKET_NAME}/{s3_key}"
            
            return jsonify({
                'success': True,
                's3_path': s3_path,
                'job_name': job_name,
                'message': 'Dataset uploaded successfully'
            })
        except Exception as e:
            return jsonify({'error': f'Failed to upload to S3: {str(e)}'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/submit-job', methods=['POST'])
def submit_job():
    """Submit a training job"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['job_name', 'input_data']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Prepare job submission
        job_data = {
            'job_name': data['job_name'],
            'image': data.get('image', TRAINING_IMAGE),
            'input_data': data['input_data'],
            'hyperparameters': data.get('hyperparameters', {
                'epochs': data.get('epochs', 10),
                'learning_rate': data.get('learning_rate', 0.001)
            })
        }
        
        # Submit to API Gateway
        response = requests.post(
            f'{API_BASE_URL}/jobs',
            json=job_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return jsonify({
                'success': True,
                'job_id': result.get('job_id'),
                'message': 'Job submitted successfully'
            })
        else:
            return jsonify({
                'error': f'Failed to submit job: {response.text}',
                'status_code': response.status_code
            }), response.status_code
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/job-status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get job status from API Gateway"""
    try:
        response = requests.get(
            f'{API_BASE_URL}/jobs/{job_id}',
            timeout=30
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({
                'error': f'Failed to get job status: {response.text}',
                'status_code': response.status_code
            }), response.status_code
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-model/<job_name>', methods=['GET'])
def download_model(job_name):
    """Generate presigned URL for model download"""
    try:
        # Model is stored at s3://bucket/models/{job_name}/model.pkl
        s3_key = f"models/{job_name}/model.pkl"
        
        # Check if model exists
        try:
            s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        except s3_client.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                return jsonify({'error': 'Model not found'}), 404
            raise
        
        # Generate presigned URL (valid for 1 hour)
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=3600
        )
        
        return jsonify({
            'success': True,
            'download_url': presigned_url,
            'job_name': job_name
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/list-jobs', methods=['GET'])
def list_jobs():
    """List all jobs by checking S3 models directory"""
    try:
        # List all models in S3
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET_NAME,
            Prefix='models/',
            Delimiter='/'
        )
        
        jobs = []
        if 'CommonPrefixes' in response:
            for prefix in response['CommonPrefixes']:
                job_name = prefix['Prefix'].replace('models/', '').rstrip('/')
                jobs.append({
                    'job_name': job_name,
                    's3_path': f"s3://{S3_BUCKET_NAME}/models/{job_name}/"
                })
        
        return jsonify({
            'success': True,
            'jobs': jobs
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(debug=True, host='0.0.0.0', port=port)

