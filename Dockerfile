# Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set Python path to include current directory
ENV PYTHONPATH=/app:$PYTHONPATH

# Install system dependencies (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# HF Spaces runs on port 7860
EXPOSE 7860

# Start FastAPI server with python -m to ensure proper module loading
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]