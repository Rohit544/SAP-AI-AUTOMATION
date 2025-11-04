"""
SAP AI Automation - Main API Application
=========================================
Path: sap-ai-automation/src/api/main.py

This is the ENTRY POINT for your FastAPI application.
Docker and Kubernetes will run this file.

Usage:
    Development:  uvicorn src.api.main:app --reload
    Production:   uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4
"""

import os
import sys
import time
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, Request, Response, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import loguru, fallback to standard logging
try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)

# Try to import Prometheus client
try:
    from prometheus_client import Counter, Histogram, make_asgi_app
    PROMETHEUS_AVAILABLE = True
    
    # Define metrics
    http_requests_total = Counter(
        'http_requests_total',
        'Total HTTP requests',
        ['method', 'endpoint', 'status']
    )
    http_request_duration = Histogram(
        'http_request_duration_seconds',
        'HTTP request duration'
    )
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("Prometheus client not available. Metrics will be disabled.")


# ============================================================================
# FastAPI Application Instance
# ============================================================================

app = FastAPI(
    title="SAP AI Automation Platform",
    description="""
    Intelligent SAP automation platform with AI/ML capabilities.
    
    ## Features
    * 🤖 AI-powered invoice processing
    * 📊 Real-time SAP integration
    * 🔄 Automated workflows
    * 📈 Process analytics
    * 🔐 Secure and compliant
    
    ## Modules
    * **FI** - Financial Accounting
    * **SD** - Sales & Distribution  
    * **MM** - Materials Management
    * **PP** - Production Planning
    * **QM** - Quality Management
    * **PM** - Plant Maintenance
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/openapi.json",
    contact={
        "name": "SAP Automation Team",
        "email": "support@example.com",
    },
    license_info={
        "name": "MIT",
    }
)


# ============================================================================
# Middleware Configuration
# ============================================================================

# CORS Middleware
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time", "X-Request-ID"]
)

# GZip Compression
app.add_middleware(
    GZipMiddleware,
    minimum_size=1000  # Only compress responses larger than 1KB
)


# Request ID and Timing Middleware
@app.middleware("http")
async def add_process_time_and_request_id(request: Request, call_next):
    """
    Add processing time and request ID to all responses
    """
    # Generate request ID
    request_id = f"{int(time.time())}-{id(request)}"
    request.state.request_id = request_id
    
    # Record start time
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - start_time
    
    # Add headers
    response.headers["X-Process-Time"] = f"{process_time:.4f}"
    response.headers["X-Request-ID"] = request_id
    
    # Log request
    logger.info(
        f"Request: {request.method} {request.url.path} | "
        f"Status: {response.status_code} | "
        f"Time: {process_time:.4f}s | "
        f"ID: {request_id}"
    )
    
    # Record Prometheus metrics
    if PROMETHEUS_AVAILABLE:
        http_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        http_request_duration.observe(process_time)
    
    return response


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle validation errors (422)
    """
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": exc.errors(),
            "body": str(exc.body) if exc.body else None,
            "request_id": getattr(request.state, "request_id", None)
        }
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Handle HTTP exceptions
    """
    logger.warning(f"HTTP error {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Error",
            "status_code": exc.status_code,
            "detail": exc.detail,
            "request_id": getattr(request.state, "request_id", None)
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Handle all other exceptions
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # In production, hide internal error details
    error_detail = str(exc) if os.getenv("ENVIRONMENT") == "development" else "Internal server error"
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "detail": error_detail,
            "request_id": getattr(request.state, "request_id", None),
            "timestamp": datetime.now().isoformat()
        }
    )


# ============================================================================
# Health Check & Status Endpoints
# ============================================================================

@app.get(
    "/",
    tags=["Root"],
    summary="Root endpoint",
    description="Returns basic API information"
)
async def root():
    """Root endpoint - API information"""
    return {
        "service": "SAP AI Automation Platform",
        "version": "1.0.0",
        "status": "running",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/health",
            "ready": "/ready",
            "metrics": "/metrics" if PROMETHEUS_AVAILABLE else None
        }
    }


@app.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    description="Returns service health status - used by Docker/Kubernetes"
)
async def health_check():
    """
    Health check endpoint
    Used by Docker HEALTHCHECK and Kubernetes liveness probe
    """
    return {
        "status": "healthy",
        "service": "sap-ai-automation",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": time.process_time()
    }


@app.get(
    "/ready",
    tags=["Health"],
    summary="Readiness check",
    description="Checks if service is ready to accept traffic"
)
async def readiness_check():
    """
    Readiness check endpoint
    Used by Kubernetes readiness probe
    Checks if all dependencies are available
    """
    checks = {
        "api": True,
        "database": None,
        "redis": None,
        "sap": None
    }
    
    all_ready = True
    
    # TODO: Add actual health checks for dependencies
    # Example:
    # try:
    #     # Check database
    #     db.execute("SELECT 1")
    #     checks["database"] = True
    # except:
    #     checks["database"] = False
    #     all_ready = False
    
    if not all_ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "checks": checks,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    return {
        "status": "ready",
        "checks": checks,
        "timestamp": datetime.now().isoformat()
    }


@app.get(
    "/info",
    tags=["Info"],
    summary="System information",
    description="Returns detailed system information"
)
async def system_info():
    """System information endpoint"""
    return {
        "application": {
            "name": "SAP AI Automation",
            "version": "1.0.0",
            "environment": os.getenv("ENVIRONMENT", "development")
        },
        "system": {
            "python_version": sys.version,
            "platform": sys.platform,
        },
        "configuration": {
            "log_level": os.getenv("LOG_LEVEL", "INFO"),
            "port": os.getenv("PORT", 8000),
            "workers": os.getenv("WORKERS", 4)
        },
        "features": {
            "prometheus_metrics": PROMETHEUS_AVAILABLE,
            "sap_integration": True,
            "ai_processing": True,
            "celery_tasks": True
        },
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# API Routes (Add your module routes here)
# ============================================================================

# Example test endpoint
@app.get(
    "/api/v1/test",
    tags=["Test"],
    summary="Test endpoint",
    description="Simple test endpoint to verify API is working"
)
async def test_endpoint():
    """Test endpoint"""
    return {
        "message": "API is working!",
        "timestamp": datetime.now().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "development")
    }


# TODO: Include your module routers here
# Uncomment these as you create the router files:
#
# from src.api.routes import fi_routes
# app.include_router(
#     fi_routes.router,
#     prefix="/api/v1/fi",
#     tags=["Financial Accounting"]
# )
#
# from src.api.routes import sd_routes
# app.include_router(
#     sd_routes.router,
#     prefix="/api/v1/sd",
#     tags=["Sales & Distribution"]
# )
#
# from src.api.routes import mm_routes
# app.include_router(
#     mm_routes.router,
#     prefix="/api/v1/mm",
#     tags=["Materials Management"]
# )


# ============================================================================
# Prometheus Metrics Endpoint
# ============================================================================

if PROMETHEUS_AVAILABLE:
    # Mount Prometheus metrics endpoint
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
    logger.info("✅ Prometheus metrics enabled at /metrics")


# ============================================================================
# Application Lifecycle Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """
    Runs when the application starts
    Initialize connections, load models, etc.
    """
    logger.info("=" * 80)
    logger.info("🚀 SAP AI Automation Platform Starting...")
    logger.info("=" * 80)
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info(f"Log Level: {os.getenv('LOG_LEVEL', 'INFO')}")
    logger.info(f"Port: {os.getenv('PORT', 8000)}")
    logger.info(f"Python: {sys.version.split()[0]}")
    
    # TODO: Initialize your services here
    # Examples:
    # - Connect to database
    # - Initialize Redis
    # - Load ML models
    # - Create SAP connection pool
    # - Initialize Celery
    
    logger.info("✅ Application started successfully!")
    logger.info(f"📚 API Docs: http://localhost:{os.getenv('PORT', 8000)}/docs")
    logger.info("=" * 80)


@app.on_event("shutdown")
async def shutdown_event():
    """
    Runs when the application shuts down
    Clean up resources, close connections, etc.
    """
    logger.info("=" * 80)
    logger.info("🛑 SAP AI Automation Platform Shutting Down...")
    logger.info("=" * 80)
    
    # TODO: Cleanup here
    # Examples:
    # - Close database connections
    # - Close SAP connections
    # - Save state if needed
    # - Stop background tasks
    
    logger.info("✅ Application stopped successfully")
    logger.info("=" * 80)


# ============================================================================
# Main Entry Point (for running directly)
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # Configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    reload = os.getenv("ENVIRONMENT", "development") == "development"
    workers = int(os.getenv("WORKERS", 1)) if not reload else 1
    log_level = os.getenv("LOG_LEVEL", "info").lower()
    
    logger.info(f"Starting server on {host}:{port}")
    logger.info(f"Reload: {reload}, Workers: {workers}, Log Level: {log_level}")
    
    # Run the application
    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        log_level=log_level,
        access_log=True,
        proxy_headers=True,
        forwarded_allow_ips="*"
    )