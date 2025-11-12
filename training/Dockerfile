FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install
COPY training/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy storage directory (needed for logger import)
# Build script now runs from root directory
COPY storage ./storage

# Copy training script
COPY training/train.py .
COPY training/test_minimal.py .

# Copy wrapper script
COPY training/run_training.sh .
RUN chmod +x run_training.sh

# Run training via wrapper
# Use bash explicitly to avoid exec format error
CMD ["/bin/bash", "run_training.sh"]