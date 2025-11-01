# ============================================================================
# SAP AI Automation - Production-Ready Dockerfile
# ============================================================================
# Path: sap-ai-automation/docker/Dockerfile
#
# Build: docker build -t sap-ai-automation:latest -f docker/Dockerfile .
# Run:   docker run -p 8000:8000 sap-ai-automation:latest
# ============================================================================

# ===== Stage 1: Builder =====
FROM continuumio/miniconda3:latest AS builder

# Set working directory
WORKDIR /app

# Install system dependencies (REQUIRED for SAP RFC SDK and other packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    make \
    curl \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy conda environment file
COPY environment.yml .

# Create conda environment
RUN conda env create -f environment.yml && \
    conda clean -afy

# Copy requirements.txt for pip packages not in conda
COPY requirements.txt .

# Install additional pip packages in conda environment
RUN /bin/bash -c "source activate sap-automation && \
    pip install --no-cache-dir -r requirements.txt"

# Copy application code
COPY . .

# Install the package in development mode
RUN /bin/bash -c "source activate sap-automation && \
    pip install -e ."

# Run tests to ensure everything is working (OPTIONAL - comment out if needed)
# RUN /bin/bash -c "source activate sap-automation && \
#     pytest tests/ -v --maxfail=1 || true"

# ===== Stage 2: Runtime =====
FROM continuumio/miniconda3:latest

# Labels for metadata
LABEL maintainer="your.email@example.com"
LABEL version="1.0.0"
LABEL description="SAP AI Automation Platform"

# Set working directory
WORKDIR /app

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # For Tesseract OCR
    tesseract-ocr \
    tesseract-ocr-eng \
    # For image processing
    libtesseract-dev \
    libleptonica-dev \
    # For PDF processing
    poppler-utils \
    # For SAP RFC (if using SAP NetWeaver RFC SDK)
    libstdc++6 \
    # For health checks
    curl \
    # For networking
    netcat-openbsd \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy conda environment from builder
COPY --from=builder /opt/conda/envs/sap-automation /opt/conda/envs/sap-automation

# Copy application code
COPY --from=builder /app /app

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/temp /app/models/trained_models /app/data && \
    chmod -R 755 /app/logs /app/temp /app/models /app/data

# Copy SAP RFC SDK if needed (UNCOMMENT if you have the SDK)
# COPY --from=builder /usr/local/sap/nwrfcsdk /usr/local/sap/nwrfcsdk
# ENV SAPNWRFC_HOME=/usr/local/sap/nwrfcsdk
# ENV LD_LIBRARY_PATH=$SAPNWRFC_HOME/lib:$LD_LIBRARY_PATH

# Set environment variables
ENV PATH=/opt/conda/envs/sap-automation/bin:$PATH \
    CONDA_DEFAULT_ENV=sap-automation \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Application settings
    ENVIRONMENT=production \
    LOG_LEVEL=INFO \
    # Port
    PORT=8000

# Expose port for API
EXPOSE 8000

# Create non-root user for security
RUN groupadd -r appuser && \
    useradd -r -g appuser -d /app -s /sbin/nologin appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Activate conda environment and run application
SHELL ["/bin/bash", "-c"]
ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "sap-automation"]

# Default command (can be overridden)
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]