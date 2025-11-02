# 🚀 SAP AI Automation Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-deployed-blue.svg)](https://kubernetes.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Intelligent SAP automation platform leveraging AI/ML to reduce manual processing time and improve efficiency.**

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Development](#development)
- [Deployment](#deployment)
- [Testing](#testing)
- [GSoC 2026 Application](#gsoc-2026-application)
- [Contributing](#contributing)

## 🎯 Overview

This project aims to automate various SAP business processes using:
- **SAP Integration**: RFC/BAPI, OData REST APIs, GUI Scripting
- **AI/ML**: Intelligent document processing, anomaly detection, process classification
- **Modern DevOps**: Docker, Kubernetes, Jenkins CI/CD
- **Scalability**: Containerized microservices architecture

**Target Use Cases:**
- Automated invoice processing with OCR + NLP
- Purchase order creation and approval workflows
- Master data management and validation
- Anomaly detection in financial transactions
- Intelligent process routing and optimization

## ✨ Features

### SAP Connectivity
- ✅ RFC/BAPI integration using PyRFC
- ✅ OData/REST API support for S/4HANA
- ✅ SAP GUI scripting for legacy systems
- ✅ Secure credential management

### AI/ML Capabilities
- 🤖 OCR-based document extraction (Tesseract + Pytesseract)
- 🧠 NLP entity recognition (spaCy)
- 📊 Process classification using Random Forest
- 🚨 Anomaly detection with Isolation Forest
- 💡 Intelligent recommendation engine

### Infrastructure
- 🐳 Docker containerization with Conda
- ☸️ Kubernetes orchestration
- 🔄 Jenkins CI/CD pipeline
- 📈 Prometheus monitoring + Grafana dashboards
- 🗄️ PostgreSQL + Redis for data persistence

## 🏗️ Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                     Client Applications                        │
│              (Web UI, Mobile Apps, API Clients)                │
└────────────────────────┬───────────────────────────────────────┘
                         │
┌────────────────────────▼───────────────────────────────────────┐
│                    API Gateway (FastAPI)                       │
│                 Load Balancer (Kubernetes)                     │
└────────────────┬────────────────────────────┬──────────────────┘
                 │                            │
     ┌───────────▼──────────┐       ┌─────────▼───────────┐
     │   SAP Connector       │       │   AI/ML Engine       │
     │  ─ RFC / BAPI         │       │  ─ OCR / NLP         │
     │  ─ REST / OData API   │       │  ─ Predictive Models │
     │  ─ GUI Scripting      │       │  ─ Anomaly Detection │
     └───────────┬───────────┘       └─────────┬────────────┘
                 │                             │
     ┌───────────▼─────────────────────────────▼────────────┐
     │             Task Queue (Celery + RabbitMQ)           │
     └───────────┬─────────────────────────────┬────────────┘
                 │                             │
     ┌───────────▼──────────────┐    ┌─────────▼────────────┐
     │   PostgreSQL Database    │    │     Redis Cache       │
     │   (Metadata, Logs)       │    │  (Sessions, Queues)   │
     └───────────┬──────────────┘    └─────────┬────────────┘
                 │                             │
     ┌───────────▼─────────────────────────────▼────────────┐
     │                     SAP Modules                     │
     │ ─ FI (Financial Accounting)                          │
     │ ─ CO (Controlling)                                   │
     │ ─ PP (Production Planning)                           │
     │ ─ PM (Plant Maintenance)                             │
     │ ─ MM (Materials Management)                          │
     │ ─ LO (Logistics)                                     │
     │ ─ LE (Logistics Execution)                           │
     │ ─ WM (Warehouse Management)                          │
     │ ─ SD (Sales & Distribution)                          │
     │ ─ QM (Quality Management)                            │
     └──────────────────────────────────────────────────────┘

```

## 📦 Prerequisites

### Required Software
- **Docker** 20.10+ & Docker Compose
- **Python** 3.11+
- **Git**
- **kubectl** (for Kubernetes deployment)
- **Jenkins** (for CI/CD)

### SAP Requirements
- SAP NetWeaver RFC SDK (for PyRFC)
- SAP GUI with scripting enabled (for GUI automation)
- SAP user with appropriate authorizations

### Optional
- **Minikube** or cloud Kubernetes cluster (GKE, EKS, AKS)
- **VS Code** with Python extension

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/Rohit544/SAP-AI-AUTOMATION.git
cd sap-ai-automation
```

### 2. Setup Environment Variables

```bash
# Copy example env file
cp config/sap_credentials.env.example config/sap_credentials.env

# Edit with your SAP credentials
nano config/sap_credentials.env
```

Add your credentials:
```env
SAP_HOST=your-sap-server.com
SAP_CLIENT=100
SAP_USER=your-username
SAP_PASSWORD=your-password
SAP_SYSTEM_NUMBER=00
```

### 3. Build and Run with Docker Compose

```bash
# Build all containers
docker-compose -f docker/docker-compose.yml build

# Start all services
docker-compose -f docker/docker-compose.yml up -d

# Check logs
docker-compose -f docker/docker-compose.yml logs -f sap-automation
```

### 4. Access Services

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Jupyter Lab**: http://localhost:8888
- **RabbitMQ Management**: http://localhost:15672 (guest/guest)
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090

### 5. Run Tests

```bash
# Run all tests
docker-compose exec sap-automation pytest tests/ -v

# Run with coverage
docker-compose exec sap-automation pytest tests/ --cov=src --cov-report=html

# Run specific test file
docker-compose exec sap-automation pytest tests/test_sap_connector.py -v
```

## ⚙️ Configuration

### Application Config (`config/config.yaml`)

```yaml
application:
  name: sap-ai-automation
  version: 1.0.0
  log_level: INFO

sap:
  connection_timeout: 30
  retry_attempts: 3
  retry_delay: 5

ai:
  model_path: /app/models/
  ocr_language: eng
  confidence_threshold: 0.7

automation:
  max_parallel_tasks: 5
  task_timeout: 600
  enable_auto_approval: false
```

### Conda Environment

The project uses Conda for dependency management. The environment is defined in `environment.yml`:

```yaml
name: sap-automation
dependencies:
  - python=3.11
  - tensorflow=2.13.0
  - scikit-learn=1.3.0
  - fastapi=0.100.0
  # ... see environment.yml for complete list
```

## 💻 Development

### Local Development Setup

```bash
# Create conda environment
conda env create -f environment.yml

# Activate environment
conda activate sap-automation

# Install in development mode
pip install -e .

# Run application locally
python -m src.main
```

### VS Code Configuration

Create `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "[python]": {
    "editor.codeActionsOnSave": {
      "source.organizeImports": true
    }
  }
}
```

### Code Style

```bash
# Format code
black src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/
```

## 🚢 Deployment

### Kubernetes Deployment

```bash
# Create namespace
kubectl create namespace sap-automation

# Apply configurations
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -f kubernetes/configmap.yaml
kubectl apply -f kubernetes/secrets.yaml
kubectl apply -f kubernetes/pvc.yaml
kubectl apply -f kubernetes/deployment.yaml
kubectl apply -f kubernetes/service.yaml
kubectl apply -f kubernetes/ingress.yaml
kubectl apply -f kubernetes/hpa.yaml

# Verify deployment
kubectl get pods -n sap-automation
kubectl get svc -n sap-automation

# Check logs
kubectl logs -f deployment/sap-automation -n sap-automation
```

### Update Deployment

```bash
# Build and push new image
docker build -t your-registry/sap-ai-automation:v1.1 .
docker push your-registry/sap-ai-automation:v1.1

# Update deployment
kubectl set image deployment/sap-automation \
  sap-automation=your-registry/sap-ai-automation:v1.1 \
  -n sap-automation

# Check rollout status
kubectl rollout status deployment/sap-automation -n sap-automation
```

### Rollback

```bash
# Rollback to previous version
kubectl rollout undo deployment/sap-automation -n sap-automation

# Rollback to specific revision
kubectl rollout undo deployment/sap-automation --to-revision=2 -n sap-automation
```

## 🧪 Testing

### Test Structure

```
tests/
├── unit/
│   ├── test_sap_connector.py
│   ├── test_ai_engine.py
│   └── test_utils.py
├── integration/
│   ├── test_sap_integration.py
│   └── test_api_endpoints.py
└── e2e/
    └── test_invoice_workflow.py
```

### Run Tests

```bash
# All tests
pytest tests/

# Unit tests only
pytest tests/unit/

# Integration tests
pytest tests/integration/

# With coverage
pytest tests/ --cov=src --cov-report=html --cov-report=term

# Specific test
pytest tests/unit/test_sap_connector.py::test_rfc_connection -v
```

## 📝 GSoC 2026 Application

### Project Proposal

**Title**: SAP Intelligent Automation Platform with AI/ML Integration

**Abstract**: 
This project addresses the critical need for automating repetitive SAP business processes. By combining traditional SAP connectivity (RFC, REST APIs) with modern AI/ML techniques (OCR, NLP, anomaly detection), we can significantly reduce manual processing time and errors.

**Key Innovations**:
1. **Hybrid Integration**: Supports legacy (RFC/GUI) and modern (REST/OData) SAP systems
2. **AI-Powered Processing**: Intelligent document extraction and classification
3. **Cloud-Native Architecture**: Containerized, scalable, production-ready
4. **Developer-Friendly**: Complete CI/CD pipeline, comprehensive testing

**Expected Impact**:
- 60-80% reduction in manual processing time
- 95%+ accuracy in document processing
- Real-time anomaly detection
- Scalable to handle enterprise workloads

### Milestones

**Phase 1 (Weeks 1-4): Foundation**
- [x] Project structure setup
- [x] Docker + Kubernetes configuration
- [x] CI/CD pipeline with Jenkins
- [ ] Basic SAP RFC connectivity
- [ ] Unit test framework

**Phase 2 (Weeks 5-8): Core Features**
- [ ] SAP REST API integration
- [ ] OCR + NLP document processing
- [ ] Process classification ML model
- [ ] Integration tests

**Phase 3 (Weeks 9-10): AI/ML Components**
- [ ] Anomaly detection system
- [ ] Recommendation engine
- [ ] Model training pipeline
- [ ] Performance optimization

**Phase 4 (Weeks 11-12): Polish & Documentation**
- [ ] End-to-end workflow tests
- [ ] Performance benchmarking
- [ ] Complete documentation
- [ ] Demo video and presentation

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md).

### Development Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Code Review Checklist

- [ ] Code follows project style guidelines
- [ ] All tests pass
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] No security vulnerabilities introduced

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- SAP Community for RFC SDK and API documentation
- TensorFlow and scikit-learn teams for ML frameworks
- Docker and Kubernetes communities
- GSoC mentors and organizers

## 📞 Contact

**Project Maintainer**: Your Name
- Email: monuoo1009@gmail.com
- GitHub: https://github.com/Rohit544
- LinkedIn: https://www.linkedin.com/in/rohitsojha/

**Project Link**: https://github.com/Rohit544/SAP-AI-AUTOMATION.git

---

⭐ Star this repo if you find it helpful!

**For GSoC 2026 applicants**: Feel free to reach out for collaboration or mentorship opportunities!

## Quick Setup

```bash
# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install SAP NW RFC SDK (required for pyrfc)
# Download from: https://support.sap.com/swdc

# 4. Configure SAP credentials
cp config/sap_credentials.env.example config/sap_credentials.env
# Edit config/sap_credentials.env with your SAP details

# 5. Run application
python -m uvicorn src.api.main:app --reload

# 6. Run tests
pytest tests/ -v
```

## Installation Issues?

If you get errors installing pyrfc:
1. Install SAP NetWeaver RFC SDK first
2. Set environment variables:
   ```bash
   export SAPNWRFC_HOME=/usr/local/sap/nwrfcsdk
   export LD_LIBRARY_PATH=$SAPNWRFC_HOME/lib:$LD_LIBRARY_PATH
   ```
3. Then: `pip install pyrfc`
