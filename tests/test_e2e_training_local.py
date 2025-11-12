"""
Local end-to-end test for model training (mocks AWS services)
Tests the complete training workflow without requiring actual AWS infrastructure
"""

import pytest
import os
import tempfile
import pickle
import pandas as pd
import boto3
from moto import mock_s3, mock_dynamodb
from unittest.mock import patch

# Import training functions
from training.train import (
    download_data_from_s3,
    load_training_data,
    create_model,
    train_model,
    save_model,
    load_model,
    get_config
)


@pytest.fixture
def sample_regression_data():
    """Create sample regression data"""
    data = {
        'feature1': [i * 0.5 for i in range(1, 101)],
        'feature2': [i * 1.2 for i in range(1, 101)],
        'feature3': [i * 2.1 for i in range(1, 101)],
        'target': [i * 2.0 + 1.5 for i in range(1, 101)]  # Linear relationship
    }
    return pd.DataFrame(data)


@pytest.fixture
def sample_classification_data():
    """Create sample classification data"""
    data = {
        'feature1': [i for i in range(1, 101)],
        'feature2': [i * 2 for i in range(1, 101)],
        'feature3': [i * 3 for i in range(1, 101)],
        'target': [0 if i < 50 else 1 for i in range(1, 101)]  # Binary classification
    }
    return pd.DataFrame(data)


@mock_s3
def test_e2e_regression_training(sample_regression_data):
    """Test complete regression training workflow"""
    print("\n" + "="*60)
    print("🧪 E2E Regression Training Test")
    print("="*60)
    
    # Setup S3
    s3_client = boto3.client('s3', region_name='us-east-1')
    bucket_name = 'test-bucket'
    s3_client.create_bucket(Bucket=bucket_name)
    
    # Upload test data to S3
    csv_content = sample_regression_data.to_csv(index=False)
    s3_key = 'data/regression_test.csv'
    s3_client.put_object(Bucket=bucket_name, Key=s3_key, Body=csv_content.encode())
    s3_input = f's3://{bucket_name}/{s3_key}'
    
    print(f"✅ Test data uploaded to {s3_input}")
    
    # Create config
    config = {
        'job_id': 'test-regression-job',
        'hyperparams': {
            'task_type': 'regression',
            'algorithm': 'linear',
            'target_column': 'target',
            'test_size': 0.2,
            'random_state': 42
        },
        's3_input': s3_input
    }
    
    # Train model
    print("🚀 Starting model training...")
    result = train_model(config)
    
    # Verify results
    assert result is not None
    assert 'model' in result
    assert 'metrics' in result
    assert 'mse' in result['metrics']
    assert 'mae' in result['metrics']
    assert 'r2_score' in result['metrics']
    
    print(f"✅ Model trained successfully!")
    print(f"   MSE: {result['metrics']['mse']:.4f}")
    print(f"   MAE: {result['metrics']['mae']:.4f}")
    print(f"   R² Score: {result['metrics']['r2_score']:.4f}")
    
    # Save model
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as f:
        model_path = f.name
    
    try:
        model_metadata = {
            'model': result['model'],
            'metrics': result['metrics'],
            'feature_columns': result.get('feature_columns', []),
            'task_type': result.get('task_type'),
            'algorithm': result.get('algorithm'),
            'job_id': config['job_id'],
            'hyperparams': config['hyperparams']
        }
        save_model(model_metadata, model_path)
        print(f"✅ Model saved to {model_path}")
        
        # Load model
        loaded = load_model(model_path)
        assert loaded is not None
        assert 'model' in loaded
        assert 'metrics' in loaded
        print("✅ Model loaded successfully")
        
        # Verify model can make predictions
        # Create test data
        test_X = pd.DataFrame({
            'feature1': [10.0],
            'feature2': [24.0],
            'feature3': [42.0]
        })
        predictions = loaded['model'].predict(test_X)
        assert len(predictions) == 1
        print(f"✅ Model can make predictions: {predictions[0]:.4f}")
        
    finally:
        if os.path.exists(model_path):
            os.unlink(model_path)
    
    print("="*60)
    print("✅ E2E Regression Test PASSED!")
    print("="*60)


@mock_s3
def test_e2e_classification_training(sample_classification_data):
    """Test complete classification training workflow"""
    print("\n" + "="*60)
    print("🧪 E2E Classification Training Test")
    print("="*60)
    
    # Setup S3
    s3_client = boto3.client('s3', region_name='us-east-1')
    bucket_name = 'test-bucket'
    s3_client.create_bucket(Bucket=bucket_name)
    
    # Upload test data to S3
    csv_content = sample_classification_data.to_csv(index=False)
    s3_key = 'data/classification_test.csv'
    s3_client.put_object(Bucket=bucket_name, Key=s3_key, Body=csv_content.encode())
    s3_input = f's3://{bucket_name}/{s3_key}'
    
    print(f"✅ Test data uploaded to {s3_input}")
    
    # Create config
    config = {
        'job_id': 'test-classification-job',
        'hyperparams': {
            'task_type': 'classification',
            'algorithm': 'random_forest',
            'target_column': 'target',
            'test_size': 0.2,
            'n_estimators': 10,
            'random_state': 42
        },
        's3_input': s3_input
    }
    
    # Train model
    print("🚀 Starting model training...")
    result = train_model(config)
    
    # Verify results
    assert result is not None
    assert 'model' in result
    assert 'metrics' in result
    assert 'accuracy' in result['metrics']
    assert 'precision' in result['metrics']
    assert 'recall' in result['metrics']
    assert 'f1_score' in result['metrics']
    
    print(f"✅ Model trained successfully!")
    print(f"   Accuracy: {result['metrics']['accuracy']:.4f}")
    print(f"   Precision: {result['metrics']['precision']:.4f}")
    print(f"   Recall: {result['metrics']['recall']:.4f}")
    print(f"   F1 Score: {result['metrics']['f1_score']:.4f}")
    
    # Save model
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as f:
        model_path = f.name
    
    try:
        model_metadata = {
            'model': result['model'],
            'metrics': result['metrics'],
            'feature_columns': result.get('feature_columns', []),
            'task_type': result.get('task_type'),
            'algorithm': result.get('algorithm'),
            'job_id': config['job_id'],
            'hyperparams': config['hyperparams']
        }
        save_model(model_metadata, model_path)
        print(f"✅ Model saved to {model_path}")
        
        # Load model
        loaded = load_model(model_path)
        assert loaded is not None
        assert 'model' in loaded
        print("✅ Model loaded successfully")
        
        # Verify model can make predictions
        test_X = pd.DataFrame({
            'feature1': [10],
            'feature2': [20],
            'feature3': [30]
        })
        predictions = loaded['model'].predict(test_X)
        assert len(predictions) == 1
        assert predictions[0] in [0, 1]
        print(f"✅ Model can make predictions: {predictions[0]}")
        
    finally:
        if os.path.exists(model_path):
            os.unlink(model_path)
    
    print("="*60)
    print("✅ E2E Classification Test PASSED!")
    print("="*60)


@mock_s3
def test_e2e_all_algorithms_regression(sample_regression_data):
    """Test all regression algorithms"""
    print("\n" + "="*60)
    print("🧪 E2E Test: All Regression Algorithms")
    print("="*60)
    
    algorithms = ['linear', 'random_forest', 'gradient_boosting', 'svm']
    
    # Setup S3
    s3_client = boto3.client('s3', region_name='us-east-1')
    bucket_name = 'test-bucket'
    s3_client.create_bucket(Bucket=bucket_name)
    
    csv_content = sample_regression_data.to_csv(index=False)
    
    for algorithm in algorithms:
        print(f"\n📊 Testing {algorithm}...")
        
        s3_key = f'data/test_{algorithm}.csv'
        s3_client.put_object(Bucket=bucket_name, Key=s3_key, Body=csv_content.encode())
        s3_input = f's3://{bucket_name}/{s3_key}'
        
        config = {
            'job_id': f'test-{algorithm}-job',
            'hyperparams': {
                'task_type': 'regression',
                'algorithm': algorithm,
                'target_column': 'target',
                'test_size': 0.2,
                'n_estimators': 10 if algorithm in ['random_forest', 'gradient_boosting'] else None,
                'random_state': 42
            },
            's3_input': s3_input
        }
        
        result = train_model(config)
        
        assert result is not None
        assert 'metrics' in result
        assert 'r2_score' in result['metrics']
        
        print(f"   ✅ {algorithm}: R² = {result['metrics']['r2_score']:.4f}, MSE = {result['metrics']['mse']:.4f}")
    
    print("="*60)
    print("✅ All Regression Algorithms Test PASSED!")
    print("="*60)


@mock_s3
def test_e2e_all_algorithms_classification(sample_classification_data):
    """Test all classification algorithms"""
    print("\n" + "="*60)
    print("🧪 E2E Test: All Classification Algorithms")
    print("="*60)
    
    algorithms = ['linear', 'random_forest', 'gradient_boosting', 'svm']
    
    # Setup S3
    s3_client = boto3.client('s3', region_name='us-east-1')
    bucket_name = 'test-bucket'
    s3_client.create_bucket(Bucket=bucket_name)
    
    csv_content = sample_classification_data.to_csv(index=False)
    
    for algorithm in algorithms:
        print(f"\n📊 Testing {algorithm}...")
        
        s3_key = f'data/test_{algorithm}.csv'
        s3_client.put_object(Bucket=bucket_name, Key=s3_key, Body=csv_content.encode())
        s3_input = f's3://{bucket_name}/{s3_key}'
        
        config = {
            'job_id': f'test-{algorithm}-job',
            'hyperparams': {
                'task_type': 'classification',
                'algorithm': algorithm,
                'target_column': 'target',
                'test_size': 0.2,
                'n_estimators': 10 if algorithm in ['random_forest', 'gradient_boosting'] else None,
                'random_state': 42
            },
            's3_input': s3_input
        }
        
        result = train_model(config)
        
        assert result is not None
        assert 'metrics' in result
        assert 'accuracy' in result['metrics']
        
        print(f"   ✅ {algorithm}: Accuracy = {result['metrics']['accuracy']:.4f}, F1 = {result['metrics']['f1_score']:.4f}")
    
    print("="*60)
    print("✅ All Classification Algorithms Test PASSED!")
    print("="*60)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

