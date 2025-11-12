import pytest
import os
import json
import pickle

def test_training_script_reads_env_vars():
    """Test training script reads environment variables"""
    os.environ['JOB_ID'] = 'test-job-123'
    os.environ['HYPERPARAMS'] = json.dumps({'epochs': 5, 'lr': 0.001})
    os.environ['S3_INPUT'] = 's3://bucket/data'
    os.environ['S3_OUTPUT'] = 's3://bucket/output'

    # Import after setting env vars
    from training.train import get_config

    config = get_config()

    assert config['job_id'] == 'test-job-123'
    assert config['hyperparams']['epochs'] == 5
    assert config['hyperparams']['lr'] == 0.001
    assert config['s3_input'] == 's3://bucket/data'
    assert config['s3_output'] == 's3://bucket/output'

def test_training_script_handles_missing_hyperparams():
    """Test training script with missing hyperparams env var"""
    os.environ['JOB_ID'] = 'test-job'
    if 'HYPERPARAMS' in os.environ:
        del os.environ['HYPERPARAMS']

    from training.train import get_config

    config = get_config()

    assert config['hyperparams'] == {}

def test_save_model_creates_file():
    """Test that save_model creates a pickle file"""
    import tempfile
    from training.train import save_model

    # Create temp model
    model_data = {'weights': [1, 2, 3], 'trained': True}

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, 'model.pkl')
        save_model(model_data, output_path)

        assert os.path.exists(output_path)

        # Verify can load it back
        with open(output_path, 'rb') as f:
            loaded = pickle.load(f)

        assert loaded['weights'] == [1, 2, 3]
        assert loaded['trained'] is True

def test_load_model_from_file():
    """Test loading a saved model"""
    import tempfile
    from training.train import save_model, load_model

    model_data = {'accuracy': 0.95}

    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = os.path.join(tmpdir, 'model.pkl')
        save_model(model_data, model_path)

        loaded = load_model(model_path)

        assert loaded['accuracy'] == 0.95