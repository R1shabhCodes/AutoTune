FROM python:3.11-slim

WORKDIR /app

# Install CPU-only PyTorch first to reduce download size and prevent timeouts
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu --no-cache-dir

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download and cache the sentence-transformers model during build
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

EXPOSE 8501

ENTRYPOINT ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
