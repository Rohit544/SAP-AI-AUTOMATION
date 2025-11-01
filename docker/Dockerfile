# Multi-stage Dockerfile with Conda for SAP AI Automation
FROM continuumio/miniconda3:latest AS builder

# Set working directory
WORKDIR /app

# Copy conda environment file
COPY environment.yml .

# Create conda environment
RUN conda env create -f environment.yml && \
    conda clean -afy

# Copy application code
COPY . .

# Install the package
RUN /bin/bash -c "source activate sap-automation && \
    pip install -e ."

# Runtime stage
FROM continuumio/miniconda3:latest

WORKDIR /app

# Copy conda environment from builder
COPY --from=builder /opt/conda/envs/sap-automation /opt/conda/envs/sap-automation

# Copy application code
COPY . .

# Set environment variables
ENV PATH=/opt/conda/envs/sap-automation/bin:$PATH
ENV CONDA_DEFAULT_ENV=sap-automation

# Expose port for API
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Activate conda environment and run application
SHELL ["/bin/bash", "-c"]
ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "sap-automation"]
CMD ["python", "-m", "src.main"]