import pytest
import os
import tempfile
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
import boto3
from moto import mock_s3

# Import functions to test (will be available after implementation)
# from training.train import download_data_from_s3, load_training_data, create_model, train_model


@pytest.fixture
def sample_regression_csv():
    """Create a sample CSV file for regression testing"""
    data = {
        'feature1': [0.5, 0.8, 1.2, 1.5, 2.0, 2.3, 2.8, 3.1, 3.5, 4.0],
        'feature2': [1.2, 1.5, 2.0, 2.3, 2.8, 3.1, 3.5, 3.9, 4.2, 4.8],
        'feature3': [2.1, 2.3, 3.1, 3.5, 4.2, 4.8, 5.2, 5.8, 6.3, 7.1],
        'target': [1.5, 2.1, 2.8, 3.2, 4.1, 4.9, 5.6, 6.2, 6.9, 7.8]
    }
    df = pd.DataFrame(data)
    return df


@pytest.fixture
def sample_classification_csv():
    """Create a sample CSV file for classification testing"""
    data = {
        'feature1': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        'feature2': [2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
        'feature3': [3, 6, 9, 12, 15, 18, 21, 24, 27, 30],
        'target': [0, 0, 0, 0, 0, 1, 1, 1, 1, 1]
    }
    df = pd.DataFrame(data)
    return df


@pytest.fixture
def temp_csv_file(sample_regression_csv):
    """Create a temporary CSV file"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        sample_regression_csv.to_csv(f.name, index=False)
        yield f.name
    os.unlink(f.name)


class TestDownloadDataFromS3:
    """Test download_data_from_s3() function"""

    @mock_s3
    def test_download_data_from_s3_success(self):
        """Test successful download from S3"""
        from training.train import download_data_from_s3
        
        # Setup S3
        s3_client = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'test-bucket'
        s3_client.create_bucket(Bucket=bucket_name)
        
        # Create test CSV data
        csv_content = 'feature1,feature2,feature3,target\n1,2,3,4\n5,6,7,8'
        s3_client.put_object(Bucket=bucket_name, Key='data/train.csv', Body=csv_content.encode())
        
        # Download
        s3_path = f's3://{bucket_name}/data/train.csv'
        local_path = download_data_from_s3(s3_path)
        
        # Verify
        assert local_path is not None
        assert os.path.exists(local_path)
        with open(local_path, 'r') as f:
            content = f.read()
            assert 'feature1,feature2,feature3,target' in content
        os.unlink(local_path)

    @mock_s3
    def test_download_data_from_s3_invalid_path(self):
        """Test error handling for invalid S3 path"""
        from training.train import download_data_from_s3
        
        # Invalid path (not s3:// format)
        invalid_path = 'invalid-path'
        with pytest.raises(ValueError):
            download_data_from_s3(invalid_path)

    @mock_s3
    def test_download_data_from_s3_missing_file(self):
        """Test error handling for missing file in S3"""
        from training.train import download_data_from_s3
        
        # Setup S3 bucket but no file
        s3_client = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'test-bucket'
        s3_client.create_bucket(Bucket=bucket_name)
        
        # Try to download non-existent file
        s3_path = f's3://{bucket_name}/data/nonexistent.csv'
        with pytest.raises(Exception):  # Should raise ClientError or similar
            download_data_from_s3(s3_path)

    @mock_s3
    def test_download_data_from_s3_path_parsing(self):
        """Test S3 path parsing (s3://bucket/key)"""
        from training.train import download_data_from_s3
        
        # Setup S3
        s3_client = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'test-bucket'
        s3_client.create_bucket(Bucket=bucket_name)
        
        csv_content = 'feature1,target\n1,2'
        s3_client.put_object(Bucket=bucket_name, Key='nested/path/data.csv', Body=csv_content.encode())
        
        # Download with nested path
        s3_path = f's3://{bucket_name}/nested/path/data.csv'
        local_path = download_data_from_s3(s3_path)
        
        assert local_path is not None
        assert os.path.exists(local_path)
        os.unlink(local_path)


class TestLoadTrainingData:
    """Test load_training_data() function"""

    def test_load_training_data_explicit_target_column(self, temp_csv_file):
        """Test CSV loading with explicit target column"""
        from training.train import load_training_data
        
        X, y, feature_columns = load_training_data(temp_csv_file, target_column='target')
        
        # Verify
        assert X is not None
        assert y is not None
        assert len(X.columns) == 3  # feature1, feature2, feature3
        assert 'target' not in X.columns
        assert len(y) == 10
        assert 'feature1' in X.columns
        assert 'feature2' in X.columns
        assert 'feature3' in X.columns

    def test_load_training_data_default_target_column(self, temp_csv_file):
        """Test CSV loading with default target column (last column)"""
        from training.train import load_training_data
        
        X, y, feature_columns = load_training_data(temp_csv_file)
        
        # Verify (should use last column 'target' by default)
        assert X is not None
        assert y is not None
        assert len(X.columns) == 3
        assert 'target' not in X.columns

    def test_load_training_data_missing_target_column(self, temp_csv_file):
        """Test handling of missing target column"""
        from training.train import load_training_data
        
        with pytest.raises(ValueError):
            load_training_data(temp_csv_file, target_column='nonexistent')

    def test_load_training_data_empty_csv(self):
        """Test handling of empty CSV"""
        from training.train import load_training_data
        
        # Create empty CSV
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write('feature1,feature2,target\n')
            empty_csv = f.name
        
        try:
            with pytest.raises(ValueError):
                load_training_data(empty_csv)
        finally:
            os.unlink(empty_csv)

    def test_load_training_data_feature_target_separation(self, sample_regression_csv):
        """Test feature/target separation"""
        from training.train import load_training_data
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            sample_regression_csv.to_csv(f.name, index=False)
            csv_path = f.name
        
        try:
            X, y, feature_columns = load_training_data(csv_path, target_column='target')
            
            # Verify separation
            assert X.shape[1] == 3  # 3 features
            assert len(y) == 10  # 10 samples
            assert list(X.columns) == ['feature1', 'feature2', 'feature3']
            assert list(y) == list(sample_regression_csv['target'])
        finally:
            os.unlink(csv_path)


class TestCreateModel:
    """Test create_model() function"""

    def test_create_model_classification_random_forest(self):
        """Test creating RandomForestClassifier"""
        from training.train import create_model
        from sklearn.ensemble import RandomForestClassifier
        
        hyperparams = {'n_estimators': 50, 'max_depth': 5}
        model = create_model('classification', 'random_forest', hyperparams)
        
        assert isinstance(model, RandomForestClassifier)
        assert model.n_estimators == 50
        assert model.max_depth == 5

    def test_create_model_classification_linear(self):
        """Test creating LogisticRegression"""
        from training.train import create_model
        from sklearn.linear_model import LogisticRegression
        
        hyperparams = {'C': 1.0}
        model = create_model('classification', 'linear', hyperparams)
        
        assert isinstance(model, LogisticRegression)

    def test_create_model_classification_gradient_boosting(self):
        """Test creating GradientBoostingClassifier"""
        from training.train import create_model
        from sklearn.ensemble import GradientBoostingClassifier
        
        hyperparams = {'n_estimators': 100, 'learning_rate': 0.1}
        model = create_model('classification', 'gradient_boosting', hyperparams)
        
        assert isinstance(model, GradientBoostingClassifier)
        assert model.n_estimators == 100
        assert model.learning_rate == 0.1

    def test_create_model_classification_svm(self):
        """Test creating SVC"""
        from training.train import create_model
        from sklearn.svm import SVC
        
        hyperparams = {'C': 1.0, 'kernel': 'rbf'}
        model = create_model('classification', 'svm', hyperparams)
        
        assert isinstance(model, SVC)
        assert model.C == 1.0
        assert model.kernel == 'rbf'

    def test_create_model_regression_random_forest(self):
        """Test creating RandomForestRegressor"""
        from training.train import create_model
        from sklearn.ensemble import RandomForestRegressor
        
        hyperparams = {'n_estimators': 100}
        model = create_model('regression', 'random_forest', hyperparams)
        
        assert isinstance(model, RandomForestRegressor)

    def test_create_model_regression_linear(self):
        """Test creating LinearRegression"""
        from training.train import create_model
        from sklearn.linear_model import LinearRegression
        
        hyperparams = {'fit_intercept': True}
        model = create_model('regression', 'linear', hyperparams)
        
        assert isinstance(model, LinearRegression)

    def test_create_model_regression_gradient_boosting(self):
        """Test creating GradientBoostingRegressor"""
        from training.train import create_model
        from sklearn.ensemble import GradientBoostingRegressor
        
        hyperparams = {'n_estimators': 50, 'max_depth': 3}
        model = create_model('regression', 'gradient_boosting', hyperparams)
        
        assert isinstance(model, GradientBoostingRegressor)

    def test_create_model_regression_svm(self):
        """Test creating SVR"""
        from training.train import create_model
        from sklearn.svm import SVR
        
        hyperparams = {'C': 1.0}
        model = create_model('regression', 'svm', hyperparams)
        
        assert isinstance(model, SVR)

    def test_create_model_invalid_algorithm(self):
        """Test invalid algorithm"""
        from training.train import create_model
        
        with pytest.raises(ValueError):
            create_model('classification', 'invalid_algorithm', {})

    def test_create_model_invalid_task_type(self):
        """Test invalid task type"""
        from training.train import create_model
        
        with pytest.raises(ValueError):
            create_model('invalid_task', 'random_forest', {})

    def test_create_model_default_hyperparameters(self):
        """Test default hyperparameters"""
        from training.train import create_model
        from sklearn.ensemble import RandomForestClassifier
        
        model = create_model('classification', 'random_forest', {})
        
        assert isinstance(model, RandomForestClassifier)
        # Should use default values
        assert model.n_estimators == 100  # default


class TestTrainModel:
    """Test train_model() function"""

    @mock_s3
    def test_train_model_classification_random_forest(self, sample_classification_csv):
        """Test training classification model with RandomForest"""
        from training.train import train_model
        
        # Setup S3
        s3_client = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'test-bucket'
        s3_client.create_bucket(Bucket=bucket_name)
        
        # Upload CSV to S3
        csv_content = sample_classification_csv.to_csv(index=False)
        s3_client.put_object(Bucket=bucket_name, Key='data/train.csv', Body=csv_content.encode())
        
        # Train model
        config = {
            'job_id': 'test-job',
            'hyperparams': {
                'task_type': 'classification',
                'algorithm': 'random_forest',
                'target_column': 'target',
                'n_estimators': 10,
                'test_size': 0.3
            },
            's3_input': f's3://{bucket_name}/data/train.csv'
        }
        
        result = train_model(config)
        
        # Verify
        assert result is not None
        assert 'model' in result
        assert 'metrics' in result
        assert 'accuracy' in result['metrics']
        assert 'precision' in result['metrics']
        assert 'recall' in result['metrics']
        assert 'f1_score' in result['metrics']
        assert result['metrics']['accuracy'] >= 0.0
        assert result['metrics']['accuracy'] <= 1.0

    @mock_s3
    def test_train_model_regression_linear(self, sample_regression_csv):
        """Test training regression model with LinearRegression"""
        from training.train import train_model
        
        # Setup S3
        s3_client = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'test-bucket'
        s3_client.create_bucket(Bucket=bucket_name)
        
        # Upload CSV to S3
        csv_content = sample_regression_csv.to_csv(index=False)
        s3_client.put_object(Bucket=bucket_name, Key='data/train.csv', Body=csv_content.encode())
        
        # Train model
        config = {
            'job_id': 'test-job',
            'hyperparams': {
                'task_type': 'regression',
                'algorithm': 'linear',
                'target_column': 'target',
                'test_size': 0.3
            },
            's3_input': f's3://{bucket_name}/data/train.csv'
        }
        
        result = train_model(config)
        
        # Verify
        assert result is not None
        assert 'model' in result
        assert 'metrics' in result
        assert 'mse' in result['metrics']
        assert 'mae' in result['metrics']
        assert 'r2_score' in result['metrics']
        assert result['metrics']['mse'] >= 0.0
        assert result['metrics']['r2_score'] <= 1.0

    @mock_s3
    def test_train_model_missing_task_type(self, sample_regression_csv):
        """Test missing required hyperparameter: task_type"""
        from training.train import train_model
        
        # Setup S3
        s3_client = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'test-bucket'
        s3_client.create_bucket(Bucket=bucket_name)
        
        csv_content = sample_regression_csv.to_csv(index=False)
        s3_client.put_object(Bucket=bucket_name, Key='data/train.csv', Body=csv_content.encode())
        
        config = {
            'job_id': 'test-job',
            'hyperparams': {
                'algorithm': 'random_forest'  # Missing task_type
            },
            's3_input': f's3://{bucket_name}/data/train.csv'
        }
        
        with pytest.raises(ValueError):
            train_model(config)

    @mock_s3
    def test_train_model_missing_algorithm(self, sample_regression_csv):
        """Test missing required hyperparameter: algorithm"""
        from training.train import train_model
        
        # Setup S3
        s3_client = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'test-bucket'
        s3_client.create_bucket(Bucket=bucket_name)
        
        csv_content = sample_regression_csv.to_csv(index=False)
        s3_client.put_object(Bucket=bucket_name, Key='data/train.csv', Body=csv_content.encode())
        
        config = {
            'job_id': 'test-job',
            'hyperparams': {
                'task_type': 'regression'  # Missing algorithm
            },
            's3_input': f's3://{bucket_name}/data/train.csv'
        }
        
        with pytest.raises(ValueError):
            train_model(config)

    @mock_s3
    def test_train_model_invalid_task_type(self, sample_regression_csv):
        """Test invalid task_type"""
        from training.train import train_model
        
        # Setup S3
        s3_client = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'test-bucket'
        s3_client.create_bucket(Bucket=bucket_name)
        
        csv_content = sample_regression_csv.to_csv(index=False)
        s3_client.put_object(Bucket=bucket_name, Key='data/train.csv', Body=csv_content.encode())
        
        config = {
            'job_id': 'test-job',
            'hyperparams': {
                'task_type': 'invalid_task',
                'algorithm': 'random_forest'
            },
            's3_input': f's3://{bucket_name}/data/train.csv'
        }
        
        with pytest.raises(ValueError):
            train_model(config)

    @mock_s3
    def test_train_model_train_test_split(self, sample_regression_csv):
        """Test train/test split"""
        from training.train import train_model
        
        # Setup S3
        s3_client = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'test-bucket'
        s3_client.create_bucket(Bucket=bucket_name)
        
        csv_content = sample_regression_csv.to_csv(index=False)
        s3_client.put_object(Bucket=bucket_name, Key='data/train.csv', Body=csv_content.encode())
        
        config = {
            'job_id': 'test-job',
            'hyperparams': {
                'task_type': 'regression',
                'algorithm': 'linear',
                'target_column': 'target',
                'test_size': 0.4  # 40% test, 60% train
            },
            's3_input': f's3://{bucket_name}/data/train.csv'
        }
        
        result = train_model(config)
        
        # Verify metrics exist (means split happened)
        assert result is not None
        assert 'metrics' in result
        assert 'mse' in result['metrics']

    @mock_s3
    def test_train_model_all_classification_algorithms(self, sample_classification_csv):
        """Test all classification algorithms"""
        from training.train import train_model
        
        algorithms = ['random_forest', 'linear', 'gradient_boosting', 'svm']
        
        for algorithm in algorithms:
            # Setup S3
            s3_client = boto3.client('s3', region_name='us-east-1')
            bucket_name = f'test-bucket-{algorithm}'
            s3_client.create_bucket(Bucket=bucket_name)
            
            csv_content = sample_classification_csv.to_csv(index=False)
            s3_client.put_object(Bucket=bucket_name, Key='data/train.csv', Body=csv_content.encode())
            
            config = {
                'job_id': f'test-job-{algorithm}',
                'hyperparams': {
                    'task_type': 'classification',
                    'algorithm': algorithm,
                    'target_column': 'target',
                    'n_estimators': 10 if algorithm in ['random_forest', 'gradient_boosting'] else None
                },
                's3_input': f's3://{bucket_name}/data/train.csv'
            }
            
            result = train_model(config)
            
            assert result is not None
            assert 'model' in result
            assert 'metrics' in result
            assert 'accuracy' in result['metrics']

    @mock_s3
    def test_train_model_all_regression_algorithms(self, sample_regression_csv):
        """Test all regression algorithms"""
        from training.train import train_model
        
        algorithms = ['random_forest', 'linear', 'gradient_boosting', 'svm']
        
        for algorithm in algorithms:
            # Setup S3
            s3_client = boto3.client('s3', region_name='us-east-1')
            bucket_name = f'test-bucket-{algorithm}'
            s3_client.create_bucket(Bucket=bucket_name)
            
            csv_content = sample_regression_csv.to_csv(index=False)
            s3_client.put_object(Bucket=bucket_name, Key='data/train.csv', Body=csv_content.encode())
            
            config = {
                'job_id': f'test-job-{algorithm}',
                'hyperparams': {
                    'task_type': 'regression',
                    'algorithm': algorithm,
                    'target_column': 'target',
                    'n_estimators': 10 if algorithm in ['random_forest', 'gradient_boosting'] else None
                },
                's3_input': f's3://{bucket_name}/data/train.csv'
            }
            
            result = train_model(config)
            
            assert result is not None
            assert 'model' in result
            assert 'metrics' in result
            assert 'mse' in result['metrics']
            assert 'r2_score' in result['metrics']


class TestIntegration:
    """Integration tests for full training workflow"""

    @mock_s3
    def test_full_training_workflow_regression(self, sample_regression_csv):
        """Test full training workflow for regression"""
        from training.train import train_model, save_model
        import tempfile
        
        # Setup S3
        s3_client = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'test-bucket'
        s3_client.create_bucket(Bucket=bucket_name)
        
        csv_content = sample_regression_csv.to_csv(index=False)
        s3_client.put_object(Bucket=bucket_name, Key='data/train.csv', Body=csv_content.encode())
        
        # Train
        config = {
            'job_id': 'test-job',
            'hyperparams': {
                'task_type': 'regression',
                'algorithm': 'random_forest',
                'target_column': 'target',
                'n_estimators': 10,
                'test_size': 0.2
            },
            's3_input': f's3://{bucket_name}/data/train.csv'
        }
        
        result = train_model(config)
        
        # Save model
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as f:
            model_path = f.name
        
        try:
            save_model(result['model'], model_path)
            assert os.path.exists(model_path)
        finally:
            os.unlink(model_path)

    @mock_s3
    def test_full_training_workflow_classification(self, sample_classification_csv):
        """Test full training workflow for classification"""
        from training.train import train_model, save_model
        import tempfile
        
        # Setup S3
        s3_client = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'test-bucket'
        s3_client.create_bucket(Bucket=bucket_name)
        
        csv_content = sample_classification_csv.to_csv(index=False)
        s3_client.put_object(Bucket=bucket_name, Key='data/train.csv', Body=csv_content.encode())
        
        # Train
        config = {
            'job_id': 'test-job',
            'hyperparams': {
                'task_type': 'classification',
                'algorithm': 'random_forest',
                'target_column': 'target',
                'n_estimators': 10,
                'test_size': 0.2
            },
            's3_input': f's3://{bucket_name}/data/train.csv'
        }
        
        result = train_model(config)
        
        # Verify metrics
        assert 'metrics' in result
        assert 'accuracy' in result['metrics']
        
        # Save model
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as f:
            model_path = f.name
        
        try:
            save_model(result['model'], model_path)
            assert os.path.exists(model_path)
        finally:
            os.unlink(model_path)

