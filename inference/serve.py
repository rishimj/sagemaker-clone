"""
Flask server for model inference
Loads a trained model from S3 and serves predictions
"""
import os
import sys
import pickle
import json
import boto3
import traceback
from flask import Flask, request, jsonify
from urllib.parse import urlparse
import numpy as np
import pandas as pd

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

# Initialize Flask app
app = Flask(__name__)

# Global variables
model_data = None
logger = get_logger(__name__)

def load_model_from_s3(s3_path):
    """
    Load model from S3
    
    Args:
        s3_path: S3 path in format s3://bucket/key
        
    Returns:
        dict: Model metadata including model object
    """
    logger.info("Loading model from S3", extra={'s3_path': s3_path})
    try:
        # Parse S3 path
        parsed = urlparse(s3_path)
        if parsed.scheme != 's3':
            raise ValueError(f"Invalid S3 path format: {s3_path}. Expected format: s3://bucket/key")
        
        bucket = parsed.netloc
        key = parsed.path.lstrip('/')
        
        if not bucket or not key:
            raise ValueError(f"Invalid S3 path: {s3_path}. Bucket and key are required")
        
        logger.debug("S3 download details", extra={'bucket': bucket, 'key': key})
        
        # Download from S3
        s3_client = boto3.client('s3')
        response = s3_client.get_object(Bucket=bucket, Key=key)
        model_bytes = response['Body'].read()
        
        # Load pickle
        model_data = pickle.loads(model_bytes)
        
        logger.info("Model loaded successfully", extra={
            'model_type': type(model_data.get('model')).__name__ if isinstance(model_data, dict) else type(model_data).__name__,
            'has_metadata': isinstance(model_data, dict)
        })
        
        return model_data
        
    except Exception as e:
        logger.error("Error loading model from S3", exc_info=True, extra={'s3_path': s3_path, 'error': str(e)})
        raise

def initialize_model():
    """Initialize model on server startup"""
    global model_data
    
    model_s3_path = os.environ.get('MODEL_S3_PATH')
    if not model_s3_path:
        logger.error("MODEL_S3_PATH environment variable not set")
        raise ValueError("MODEL_S3_PATH environment variable is required")
    
    endpoint_name = os.environ.get('ENDPOINT_NAME', 'unknown')
    logger.info("Initializing inference server", extra={'endpoint_name': endpoint_name, 'model_s3_path': model_s3_path})
    
    try:
        model_data = load_model_from_s3(model_s3_path)
        logger.info("Model initialization complete", extra={'endpoint_name': endpoint_name})
    except Exception as e:
        logger.error("Failed to initialize model", exc_info=True, extra={'error': str(e)})
        raise

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for ALB"""
    if model_data is None:
        return jsonify({'status': 'unhealthy', 'error': 'Model not loaded'}), 503
    
    return jsonify({
        'status': 'healthy',
        'endpoint': os.environ.get('ENDPOINT_NAME', 'unknown'),
        'model_loaded': True
    }), 200

@app.route('/predict', methods=['POST'])
def predict():
    """
    Make predictions with the loaded model
    
    Expected input:
        {
            "features": [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]  // 2D array of features
        }
        OR
        {
            "features": [1.0, 2.0, 3.0]  // Single sample (will be converted to 2D)
        }
    
    Returns:
        {
            "predictions": [0, 1],
            "model_type": "classification"
        }
    """
    if model_data is None:
        return jsonify({'error': 'Model not loaded'}), 503
    
    try:
        # Parse request
        data = request.get_json()
        if not data or 'features' not in data:
            return jsonify({'error': 'Missing required field: features'}), 400
        
        features = data['features']
        
        # Convert to numpy array
        features_array = np.array(features)
        
        # Ensure 2D array
        if features_array.ndim == 1:
            features_array = features_array.reshape(1, -1)
        
        # Extract model from metadata
        if isinstance(model_data, dict):
            model = model_data.get('model')
            feature_columns = model_data.get('feature_columns', [])
            task_type = model_data.get('task_type', 'unknown')
            algorithm = model_data.get('algorithm', 'unknown')
            
            # Validate feature count if we have metadata
            if feature_columns and features_array.shape[1] != len(feature_columns):
                return jsonify({
                    'error': f'Expected {len(feature_columns)} features, got {features_array.shape[1]}',
                    'expected_features': feature_columns
                }), 400
        else:
            # Legacy model without metadata
            model = model_data
            task_type = 'unknown'
            algorithm = 'unknown'
            feature_columns = []
        
        # Make predictions
        predictions = model.predict(features_array)
        
        # Convert numpy types to Python types for JSON serialization
        predictions_list = predictions.tolist()
        
        response = {
            'predictions': predictions_list,
            'task_type': task_type,
            'algorithm': algorithm,
            'num_samples': len(predictions_list)
        }
        
        # Add prediction probabilities for classification if available
        if task_type == 'classification' and hasattr(model, 'predict_proba'):
            try:
                probabilities = model.predict_proba(features_array)
                response['probabilities'] = probabilities.tolist()
            except Exception as e:
                logger.warning("Could not get prediction probabilities", extra={'error': str(e)})
        
        logger.info("Prediction successful", extra={
            'num_samples': len(predictions_list),
            'task_type': task_type
        })
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error("Error making prediction", exc_info=True, extra={'error': str(e)})
        return jsonify({
            'error': 'Prediction failed',
            'message': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/model-info', methods=['GET'])
def model_info():
    """Get information about the loaded model"""
    if model_data is None:
        return jsonify({'error': 'Model not loaded'}), 503
    
    try:
        if isinstance(model_data, dict):
            info = {
                'task_type': model_data.get('task_type', 'unknown'),
                'algorithm': model_data.get('algorithm', 'unknown'),
                'feature_columns': model_data.get('feature_columns', []),
                'num_features': len(model_data.get('feature_columns', [])),
                'metrics': model_data.get('metrics', {}),
                'job_id': model_data.get('job_id', 'unknown'),
                'hyperparameters': model_data.get('hyperparams', {})
            }
        else:
            info = {
                'model_type': type(model_data).__name__,
                'message': 'Legacy model format without metadata'
            }
        
        return jsonify(info), 200
        
    except Exception as e:
        logger.error("Error getting model info", exc_info=True, extra={'error': str(e)})
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Initialize model on startup
    try:
        initialize_model()
    except Exception as e:
        logger.error("Failed to initialize model on startup", exc_info=True)
        sys.exit(1)
    
    # Start Flask server
    port = int(os.environ.get('PORT', 8080))
    logger.info("Starting Flask server", extra={'port': port})
    app.run(host='0.0.0.0', port=port, debug=False)

