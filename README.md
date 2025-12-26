# AWS SageMaker Clone

AWS SageMaker Clone: A full-stack, simplified platform for training and deploying machine learning models with web, CLI, and API access.

## What it does

- Upload datasets and train ML models through a web interface
- Submit and monitor training jobs via REST API or CLI
- Automatically saves trained models to S3
- Real-time job status tracking

## Tech Stack

- **Frontend**: Flask web UI
- **Compute**: Lambda (orchestration), ECS Fargate (training)
- **Storage**: S3 (data/models), DynamoDB (job tracking)
- **API**: API Gateway

## Quick Start

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Configure AWS credentials:

```bash
cp env.example .env
# Edit .env with your AWS account details
```

3. Deploy infrastructure:

```bash
./infrastructure/setup_all.sh
```

See `docs/QUICKSTART.md` for detailed setup instructions.

## Usage

### Web UI

```bash
cd ui
./start.sh
```

Open `http://localhost:8080` to upload datasets, train models, and download results.

### CLI

```bash
# Submit a training job
python cli/cli.py submit --name my-job --image <ecr-image> --data s3://bucket/data

# Check job status
python cli/cli.py status <job-id>
```

### REST API

```bash
# Submit job
curl -X POST https://api-url/prod/jobs \
  -H "Content-Type: application/json" \
  -d '{"job_name": "my-job", "image": "...", "input_data": "s3://..."}'

# Get status
curl https://api-url/prod/jobs/{job-id}
```

## Project Structure

```
├── infrastructure/     # AWS deployment scripts
├── lambda_functions/   # Job submission and status handlers
├── storage/           # S3 and DynamoDB utilities
├── training/          # Docker container for model training
├── ui/                # Flask web interface
├── cli/               # Command-line tool
└── tests/             # Test suite
```

## Testing

```bash
pytest tests/ -v
```

## How it works

1. User submits a job (via UI, CLI, or API)
2. Lambda creates a job record in DynamoDB
3. ECS Fargate spins up a container to train the model
4. Training container saves the model to S3
5. Job status updates to "completed"


