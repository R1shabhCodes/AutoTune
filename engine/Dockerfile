FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first to reduce download size and prevent timeouts
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu --no-cache-dir

COPY engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download and cache the sentence-transformers model during build
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy the engine folder files
COPY engine/ ./engine/
# Copy the compiled dashboard static files to the expected location
COPY dashboard/dist/ ./dashboard/dist/

WORKDIR /app/engine

EXPOSE 8000

ENTRYPOINT ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
