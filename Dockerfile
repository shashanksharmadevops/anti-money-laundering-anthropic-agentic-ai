FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY generate_synthetic_data.py tools.py orchestrator.py feedback.py ./
COPY app ./app

# Generate the synthetic dataset at build time so the image is self-contained.
# (data/feedback_log.json is created lazily at runtime by feedback.py)
RUN python generate_synthetic_data.py

EXPOSE 8000

# Run from /app so relative paths in tools.py / feedback.py resolve correctly
WORKDIR /app/app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
