FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libfaiss-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements-debate.txt requirements-rag.txt ./

# Install python dependencies
RUN pip install --no-cache-dir -r requirements-debate.txt
RUN pip install --no-cache-dir -r requirements-rag.txt

# Copy application files
COPY . .

# Create storage directories
RUN mkdir -p storage/faiss_db images doc code

# Expose ports for both Debate (5050) and RAG (5080)
EXPOSE 5050 5080

# The default command will run the bash startup script
CMD ["./run.sh"]
