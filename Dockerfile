FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libldap2-dev \
    libsasl2-dev \
    libssl-dev \
    git \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install PyTorch with CUDA support (adjust based on your GPU)
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Clone the DiffHDR model repository
RUN git clone https://github.com/huTao1030/DiffHDR-pytorch.git /app/DiffHDR-pytorch

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/media/uploads /app/media/results /app/models /app/logs

# Set permissions
RUN chmod +x /app/entrypoint.sh

# Expose port
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]