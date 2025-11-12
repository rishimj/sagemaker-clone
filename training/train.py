import os
import json
import pickle
import sys
import traceback
import tempfile
import boto3
from urllib.parse import urlparse
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.svm import SVC, SVR
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, confusion_matrix,
    mean_squared_error, mean_absolute_error, r2_score
)

# Add /app directory to path for imports (Docker container)
sys.path.insert(0, '/app')
# Also add parent directory as fallback
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

logger = get_logger(__name__)

def get_config():
    """
    Get configuration from environment variables

    Returns:
        dict: Configuration dictionary
    """
    hyperparams_str = os.environ.get('HYPERPARAMS', '{}')
    
    # Safely parse hyperparameters
    try:
        hyperparams = json.loads(hyperparams_str)
        logger.debug("Parsed hyperparameters", extra={'hyperparams': hyperparams})
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse HYPERPARAMS, using empty dict", exc_info=True, extra={'hyperparams_str': hyperparams_str})
        hyperparams = {}

    config = {
        'job_id': os.environ.get('JOB_ID', 'unknown'),
        'hyperparams': hyperparams,
        's3_input': os.environ.get('S3_INPUT', ''),
        's3_output': os.environ.get('S3_OUTPUT', ''),
        'dynamodb_table': os.environ.get('DYNAMODB_TABLE', 'ml-jobs')
    }
    
    logger.info("Configuration loaded", extra={'job_id': config['job_id'], 's3_input': config['s3_input'], 's3_output': config['s3_output']})
    return config

def save_model(model, output_path):
    """
    Save model to pickle file

    Args:
        model: Model object to save
        output_path: Path to save file
    """
    logger.info("Saving model", extra={'output_path': output_path})
    try:
        with open(output_path, 'wb') as f:
            pickle.dump(model, f)
        logger.info("Model saved successfully", extra={'output_path': output_path})
    except Exception as e:
        logger.error("Error saving model", exc_info=True, extra={'output_path': output_path, 'error': str(e)})
        raise

def load_model(model_path):
    """
    Load model from pickle file

    Args:
        model_path: Path to model file

    Returns:
        Model object
    """
    logger.info("Loading model", extra={'model_path': model_path})
    try:
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        logger.info("Model loaded successfully", extra={'model_path': model_path})
        return model
    except Exception as e:
        logger.error("Error loading model", exc_info=True, extra={'model_path': model_path, 'error': str(e)})
        raise

def download_data_from_s3(s3_path):
    """
    Download CSV file from S3 to local temporary file
    
    Args:
        s3_path: S3 path in format s3://bucket/key
        
    Returns:
        str: Local file path to downloaded CSV
    """
    logger.info("Downloading data from S3", extra={'s3_path': s3_path})
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
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(mode='w+b', suffix='.csv', delete=False)
        temp_file.close()
        local_path = temp_file.name
        
        # Download from S3
        s3_client = boto3.client('s3')
        s3_client.download_file(bucket, key, local_path)
        
        logger.info("Data downloaded successfully", extra={'s3_path': s3_path, 'local_path': local_path})
        return local_path
        
    except Exception as e:
        logger.error("Error downloading data from S3", exc_info=True, extra={'s3_path': s3_path, 'error': str(e)})
        raise


def load_training_data(csv_path, target_column=None):
    """
    Load training data from CSV file and separate features from target
    
    Args:
        csv_path: Path to CSV file
        target_column: Name of target column (default: None, uses last column)
        
    Returns:
        tuple: (X, y, feature_columns) where X is features DataFrame, y is target Series, feature_columns is list of feature names
    """
    logger.info("Loading training data", extra={'csv_path': csv_path, 'target_column': target_column})
    try:
        # Load CSV
        df = pd.read_csv(csv_path)
        
        if df.empty:
            raise ValueError("CSV file is empty")
        
        logger.debug("CSV loaded", extra={'rows': len(df), 'columns': list(df.columns)})
        
        # Determine target column
        if target_column is None:
            # Use last column as target
            target_column = df.columns[-1]
            logger.info("Using last column as target", extra={'target_column': target_column})
        
        if target_column not in df.columns:
            raise ValueError(f"Target column '{target_column}' not found in CSV. Available columns: {list(df.columns)}")
        
        # Separate features and target
        X = df.drop(columns=[target_column])
        y = df[target_column]
        feature_columns = list(X.columns)
        
        logger.info("Data loaded successfully", extra={
            'n_samples': len(X),
            'n_features': len(feature_columns),
            'target_column': target_column
        })
        
        return X, y, feature_columns
        
    except Exception as e:
        logger.error("Error loading training data", exc_info=True, extra={'csv_path': csv_path, 'error': str(e)})
        raise


def create_model(task_type, algorithm, hyperparams):
    """
    Create a sklearn model based on task type and algorithm
    
    Args:
        task_type: 'classification' or 'regression'
        algorithm: Algorithm name ('random_forest', 'linear', 'gradient_boosting', 'svm')
        hyperparams: Dictionary of hyperparameters
        
    Returns:
        sklearn model instance
    """
    logger.info("Creating model", extra={'task_type': task_type, 'algorithm': algorithm, 'hyperparams': hyperparams})
    
    # Validate task type
    if task_type not in ['classification', 'regression']:
        raise ValueError(f"Invalid task_type: {task_type}. Must be 'classification' or 'regression'")
    
    # Algorithm mapping
    algorithm_map = {
        'classification': {
            'random_forest': RandomForestClassifier,
            'linear': LogisticRegression,
            'gradient_boosting': GradientBoostingClassifier,
            'svm': SVC
        },
        'regression': {
            'random_forest': RandomForestRegressor,
            'linear': LinearRegression,
            'gradient_boosting': GradientBoostingRegressor,
            'svm': SVR
        }
    }
    
    if algorithm not in algorithm_map[task_type]:
        raise ValueError(f"Invalid algorithm '{algorithm}' for task_type '{task_type}'. "
                        f"Supported algorithms: {list(algorithm_map[task_type].keys())}")
    
    # Get model class
    model_class = algorithm_map[task_type][algorithm]
    
    # Extract hyperparameters
    model_params = {}
    
    # Algorithm-specific hyperparameters
    if algorithm == 'random_forest':
        model_params['n_estimators'] = hyperparams.get('n_estimators', 100)
        if 'max_depth' in hyperparams:
            model_params['max_depth'] = hyperparams['max_depth']
        # RandomForest supports random_state
        model_params['random_state'] = hyperparams.get('random_state', 42)
    
    elif algorithm == 'linear':
        if task_type == 'classification':
            if 'C' in hyperparams:
                model_params['C'] = hyperparams['C']
            model_params['max_iter'] = hyperparams.get('max_iter', 1000)
            # LogisticRegression supports random_state
            if 'random_state' in hyperparams:
                model_params['random_state'] = hyperparams['random_state']
        else:  # regression
            # LinearRegression does NOT support random_state
            model_params['fit_intercept'] = hyperparams.get('fit_intercept', True)
    
    elif algorithm == 'gradient_boosting':
        model_params['n_estimators'] = hyperparams.get('n_estimators', 100)
        model_params['learning_rate'] = hyperparams.get('learning_rate', 0.1)
        model_params['max_depth'] = hyperparams.get('max_depth', 3)
        # GradientBoosting supports random_state
        model_params['random_state'] = hyperparams.get('random_state', 42)
    
    elif algorithm == 'svm':
        model_params['C'] = hyperparams.get('C', 1.0)
        model_params['kernel'] = hyperparams.get('kernel', 'rbf')
        if 'gamma' in hyperparams:
            model_params['gamma'] = hyperparams['gamma']
        if task_type == 'classification':
            model_params['probability'] = hyperparams.get('probability', False)
            # SVC supports random_state
            if 'random_state' in hyperparams:
                model_params['random_state'] = hyperparams['random_state']
        # SVR does NOT support random_state
    
    # Create model instance
    model = model_class(**model_params)
    
    logger.info("Model created successfully", extra={'task_type': task_type, 'algorithm': algorithm, 'model_params': model_params})
    return model


def train_model(config):
    """
    Train a machine learning model
    
    Args:
        config: Configuration dictionary with:
            - job_id: Job identifier
            - hyperparams: Dictionary of hyperparameters (must include 'task_type' and 'algorithm')
            - s3_input: S3 path to training data
            
    Returns:
        dict: Dictionary with 'model' (trained model) and 'metrics' (evaluation metrics)
    """
    train_logger = get_logger(__name__, {'job_id': config['job_id']})
    train_logger.info("Starting model training", extra={'hyperparams': config['hyperparams']})
    
    try:
        # Validate required hyperparameters
        hyperparams = config['hyperparams']
        if 'task_type' not in hyperparams:
            raise ValueError("Required hyperparameter 'task_type' is missing. Must be 'classification' or 'regression'")
        if 'algorithm' not in hyperparams:
            raise ValueError("Required hyperparameter 'algorithm' is missing")
        
        task_type = hyperparams['task_type']
        algorithm = hyperparams['algorithm']
        
        # Validate task_type
        if task_type not in ['classification', 'regression']:
            raise ValueError(f"Invalid task_type: {task_type}. Must be 'classification' or 'regression'")
        
        # Download data from S3
        s3_input = config.get('s3_input', '')
        if not s3_input:
            raise ValueError("S3_INPUT is required but not provided")
        
        train_logger.info("Downloading training data from S3", extra={'s3_input': s3_input})
        local_csv_path = download_data_from_s3(s3_input)
        
        try:
            # Load training data
            target_column = hyperparams.get('target_column', None)
            X, y, feature_columns = load_training_data(local_csv_path, target_column=target_column)
            
            # Train/test split
            test_size = hyperparams.get('test_size', 0.2)
            random_state = hyperparams.get('random_state', 42)
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=random_state
            )
            
            train_logger.info("Data split completed", extra={
                'train_samples': len(X_train),
                'test_samples': len(X_test),
                'test_size': test_size
            })
            
            # Create model
            model = create_model(task_type, algorithm, hyperparams)
            
            # Train model
            train_logger.info("Training model", extra={'algorithm': algorithm, 'task_type': task_type})
            model.fit(X_train, y_train)
            train_logger.info("Model training completed")
            
            # Evaluate model
            y_pred = model.predict(X_test)
            
            metrics = {}
            if task_type == 'classification':
                metrics['accuracy'] = float(accuracy_score(y_test, y_pred))
                metrics['precision'] = float(precision_score(y_test, y_pred, average='weighted', zero_division=0))
                metrics['recall'] = float(recall_score(y_test, y_pred, average='weighted', zero_division=0))
                metrics['f1_score'] = float(f1_score(y_test, y_pred, average='weighted', zero_division=0))
                # Store confusion matrix as list for JSON serialization
                cm = confusion_matrix(y_test, y_pred)
                metrics['confusion_matrix'] = cm.tolist()
            else:  # regression
                metrics['mse'] = float(mean_squared_error(y_test, y_pred))
                metrics['mae'] = float(mean_absolute_error(y_test, y_pred))
                metrics['r2_score'] = float(r2_score(y_test, y_pred))
            
            train_logger.info("Model evaluation completed", extra={'metrics': metrics})
            
            # Return model and metrics
            return {
                'model': model,
                'metrics': metrics,
                'feature_columns': feature_columns,
                'task_type': task_type,
                'algorithm': algorithm
            }
            
        finally:
            # Clean up temporary file
            if os.path.exists(local_csv_path):
                os.unlink(local_csv_path)
                train_logger.debug("Cleaned up temporary CSV file", extra={'path': local_csv_path})
                
    except Exception as e:
        train_logger.error("Error in model training", exc_info=True, extra={'error': str(e)})
        raise


def train_dummy_model(config):
    """
    Train a dummy model (placeholder for real training)

    Args:
        config: Configuration dictionary

    Returns:
        dict: Trained model
    """
    train_logger = get_logger(__name__, {'job_id': config['job_id']})
    train_logger.info("Starting model training", extra={'hyperparams': config['hyperparams']})

    # Dummy training logic
    model = {
        'job_id': config['job_id'],
        'trained': True,
        'hyperparams': config['hyperparams'],
        'accuracy': 0.95  # Fake metric
    }

    train_logger.info("Model training completed", extra={'job_id': config['job_id'], 'accuracy': model['accuracy']})
    return model

def upload_to_s3(local_path, s3_path):
    """
    Upload file to S3
    
    Args:
        local_path: Local file path
        s3_path: S3 path (s3://bucket/key)
    """
    logger.info("Uploading model to S3", extra={'local_path': local_path, 's3_path': s3_path})
    try:
        parsed = urlparse(s3_path)
        bucket = parsed.netloc
        key = parsed.path.lstrip('/')
        
        # Ensure directory structure
        if not key.endswith('/'):
            key = key + '/'
        key = key + 'model.pkl'
        
        logger.debug("S3 upload details", extra={'bucket': bucket, 'key': key})
        s3_client = boto3.client('s3')
        s3_client.upload_file(local_path, bucket, key)
        logger.info("Model uploaded successfully", extra={'s3_path': f's3://{bucket}/{key}'})
        return True
    except Exception as e:
        logger.error("Error uploading to S3", exc_info=True, extra={'local_path': local_path, 's3_path': s3_path, 'error': str(e)})
        return False

def update_job_status(job_id, status, dynamodb_table='ml-jobs'):
    """
    Update job status in DynamoDB
    
    Args:
        job_id: Job identifier
        status: New status
        dynamodb_table: DynamoDB table name
    """
    status_logger = get_logger(__name__, {'job_id': job_id, 'table': dynamodb_table})
    status_logger.info("Updating job status", extra={'job_id': job_id, 'status': status, 'table': dynamodb_table})
    
    try:
        dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
        table = dynamodb.Table(dynamodb_table)
        
        table.update_item(
            Key={'job_id': job_id},
            UpdateExpression='SET #s = :status',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={':status': status}
        )
        status_logger.info("Job status updated successfully", extra={'job_id': job_id, 'status': status})
        return True
    except Exception as e:
        status_logger.error(
            "Error updating job status",
            exc_info=True,
            extra={'job_id': job_id, 'status': status, 'table': dynamodb_table, 'error': str(e)}
        )
        # Don't fail the whole job if status update fails
        return False

def main():
    """Main training function"""
    # Use print for immediate output (logger might not work)
    print("="*60, flush=True)
    print("Starting Training Job", flush=True)
    print("="*60, flush=True)
    
    try:
        print(f"Python version: {sys.version}", flush=True)
        print(f"Working directory: {os.getcwd()}", flush=True)
        print(f"Python path: {sys.path}", flush=True)
        print("", flush=True)
        
        # Check if storage directory exists
        # In Docker, storage is at /app/storage
        storage_path = '/app/storage'
        print(f"Checking storage directory: {storage_path}", flush=True)
        print(f"Storage exists: {os.path.exists(storage_path)}", flush=True)
        if os.path.exists(storage_path):
            print(f"Storage contents: {os.listdir(storage_path)}", flush=True)
        else:
            # Try alternative path
            alt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'storage')
            print(f"Trying alternative path: {alt_path}", flush=True)
            if os.path.exists(alt_path):
                print(f"Found at: {alt_path}", flush=True)
        print("", flush=True)
        
        job_id = os.environ.get('JOB_ID', 'unknown')
        print(f"Job ID: {job_id}", flush=True)
        
        # Print environment variables
        print("Environment variables:", flush=True)
        for key in ['JOB_ID', 'S3_INPUT', 'S3_OUTPUT', 'HYPERPARAMS', 'DYNAMODB_TABLE', 'AWS_REGION']:
            value = os.environ.get(key, 'NOT SET')
            print(f"  {key}={value}", flush=True)
        print("", flush=True)
        
        # Try to get logger
        try:
            main_logger = get_logger(__name__, {'job_id': job_id})
            print("✅ Logger initialized successfully", flush=True)
        except Exception as logger_error:
            print(f"⚠️  Logger initialization failed: {logger_error}", flush=True)
            import logging
            main_logger = logging.getLogger(__name__)
            main_logger.setLevel(logging.INFO)
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
            main_logger.addHandler(handler)
        
        exit_code = 0
        config = None
        
        print("Getting configuration...", flush=True)
        config = get_config()
        print(f"✅ Configuration loaded: {config}", flush=True)
        
        main_logger.info("Training job configuration", extra={
            'job_id': config['job_id'],
            'hyperparams': config['hyperparams'],
            's3_input': config['s3_input'],
            's3_output': config['s3_output'],
            'dynamodb_table': config.get('dynamodb_table', 'ml-jobs')
        })
        
        # Update status to running (optional - already set by Lambda)
        # update_job_status(config['job_id'], 'running')
        main_logger.info("Job status already set to 'running' by Lambda")
        
        # Validate required hyperparameters
        hyperparams = config.get('hyperparams', {})
        if 'task_type' not in hyperparams:
            raise ValueError("Required hyperparameter 'task_type' is missing. Must be 'classification' or 'regression'")
        if 'algorithm' not in hyperparams:
            raise ValueError("Required hyperparameter 'algorithm' is missing")
        
        # Train model
        main_logger.info("Starting model training", extra={
            'task_type': hyperparams.get('task_type'),
            'algorithm': hyperparams.get('algorithm')
        })
        training_result = train_model(config)
        main_logger.info("Model training completed", extra={'metrics': training_result.get('metrics', {})})
        
        # Extract model and metrics
        model = training_result['model']
        metrics = training_result['metrics']
        
        # Create model metadata for saving
        model_metadata = {
            'model': model,
            'metrics': metrics,
            'feature_columns': training_result.get('feature_columns', []),
            'task_type': training_result.get('task_type'),
            'algorithm': training_result.get('algorithm'),
            'job_id': config['job_id'],
            'hyperparams': hyperparams
        }
        
        # Save model locally
        local_model_path = '/tmp/model.pkl'
        main_logger.info("Saving model locally", extra={'path': local_model_path})
        save_model(model_metadata, local_model_path)
        
        # Upload to S3
        main_logger.info("Uploading model to S3", extra={'s3_output': config['s3_output']})
        s3_upload_success = upload_to_s3(local_model_path, config['s3_output'])
        if s3_upload_success:
            main_logger.info("Model uploaded successfully")
        else:
            main_logger.warning("Model upload failed, but continuing")
        
        # Update status to completed
        main_logger.info("Updating job status to 'completed'")
        status_update_success = update_job_status(
            config['job_id'], 
            'completed', 
            config.get('dynamodb_table', 'ml-jobs')
        )
        if status_update_success:
            main_logger.info("Status updated successfully")
        else:
            main_logger.warning("Status update failed, but training completed")
            exit_code = 0  # Don't fail if status update fails
        
        main_logger.info("="*60)
        main_logger.info("Training complete!")
        main_logger.info("="*60)
        
    except KeyboardInterrupt:
        print("⚠️  Training interrupted by user", flush=True)
        try:
            if 'main_logger' in locals():
                main_logger.warning("Training interrupted by user")
        except:
            pass
        exit_code = 130
    except Exception as e:
        print(f"❌ Error in training: {e}", flush=True)
        print("="*60, flush=True)
        print("TRACEBACK:", flush=True)
        print("="*60, flush=True)
        import traceback
        traceback.print_exc(file=sys.stdout)
        print("="*60, flush=True)
        try:
            if 'main_logger' in locals():
                main_logger.error("Error in training", exc_info=True, extra={'error': str(e), 'job_id': job_id})
        except:
            pass  # Logger might not work
        exit_code = 1
        
        # Update status to failed
        try:
            job_id = os.environ.get('JOB_ID', 'unknown')
            table = config.get('dynamodb_table', 'ml-jobs') if config else 'ml-jobs'
            if 'main_logger' in locals():
                main_logger.info("Attempting to update job status to 'failed'")
            update_job_status(job_id, 'failed', table)
        except Exception as update_error:
            print(f"⚠️  Could not update status to failed: {update_error}", flush=True)
            try:
                if 'main_logger' in locals():
                    main_logger.error("Could not update status to failed", exc_info=True, extra={'error': str(update_error)})
            except:
                pass
    
    finally:
        try:
            if 'main_logger' in locals():
                main_logger.info("Exiting", extra={'exit_code': exit_code})
            else:
                print(f"Exiting with code: {exit_code}", flush=True)
        except:
            print(f"Exiting with code: {exit_code}", flush=True)
        # Ensure exit code is in valid range (0-255)
        # Don't use os._exit as it can cause issues with exit code 255
        final_exit_code = max(0, min(255, exit_code))
        print(f"Final exit code: {final_exit_code}", flush=True)
        sys.exit(final_exit_code)

if __name__ == '__main__':
    try:
        # Force unbuffered output
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(line_buffering=True)
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(line_buffering=True)
        
        print("="*60, flush=True)
        print("Python script starting...", flush=True)
        print(f"Python version: {sys.version}", flush=True)
        print(f"Script path: {__file__}", flush=True)
        print("="*60, flush=True)
        
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user", flush=True)
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ FATAL ERROR in main: {e}", flush=True)
        import traceback
        print("="*60, flush=True)
        print("FATAL TRACEBACK:", flush=True)
        print("="*60, flush=True)
        traceback.print_exc(file=sys.stdout)
        print("="*60, flush=True)
        sys.exit(1)