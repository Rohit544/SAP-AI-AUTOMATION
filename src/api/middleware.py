"""
API Middleware - Rate Limiting, Authentication, Logging
========================================================
Path: sap-ai-automation/src/api/middleware.py

Middleware functions that process requests before they reach endpoints
"""

import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Callable, Optional, Dict
from functools import wraps

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# ============================================================================
# Rate Limiting with Token Bucket Algorithm
# ============================================================================

class TokenBucket:
    """
    Token Bucket Algorithm for Rate Limiting
    
    DSA: Queue-based token bucket
    Complexity: O(1) for each request
    """
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Args:
            capacity: Maximum tokens in bucket
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
    
    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from bucket
        
        Returns:
            True if tokens available, False otherwise
        """
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def _refill(self):
        """Refill tokens based on time elapsed"""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        
        self.last_refill = now
    
    def get_wait_time(self) -> float:
        """Get time to wait before next request allowed"""
        if self.tokens >= 1:
            return 0.0
        return (1 - self.tokens) / self.refill_rate


class RateLimiter:
    """
    Rate Limiter using Token Bucket per client
    
    Usage:
        rate_limiter = RateLimiter(requests_per_minute=60)
        if not rate_limiter.is_allowed(client_id):
            raise HTTPException(429, "Rate limit exceeded")
    """
    
    def __init__(self, requests_per_minute: int = 60):
        """
        Args:
            requests_per_minute: Maximum requests allowed per minute
        """
        self.buckets: Dict[str, TokenBucket] = {}
        self.requests_per_minute = requests_per_minute
        
        # Token bucket parameters
        self.capacity = requests_per_minute
        self.refill_rate = requests_per_minute / 60.0  # tokens per second
    
    def is_allowed(self, client_id: str) -> bool:
        """
        Check if request is allowed for client
        
        Args:
            client_id: Unique identifier (IP, user_id, API key)
        
        Returns:
            True if allowed, False if rate limited
        """
        # Create bucket if doesn't exist
        if client_id not in self.buckets:
            self.buckets[client_id] = TokenBucket(
                capacity=self.capacity,
                refill_rate=self.refill_rate
            )
        
        bucket = self.buckets[client_id]
        return bucket.consume(1)
    
    def get_retry_after(self, client_id: str) -> float:
        """Get seconds to wait before retry"""
        if client_id not in self.buckets:
            return 0.0
        return self.buckets[client_id].get_wait_time()
    
    def cleanup_old_buckets(self):
        """Remove inactive buckets (call periodically)"""
        now = time.time()
        to_remove = []
        
        for client_id, bucket in self.buckets.items():
            if (now - bucket.last_refill) > 3600:  # 1 hour inactive
                to_remove.append(client_id)
        
        for client_id in to_remove:
            del self.buckets[client_id]


# ============================================================================
# Rate Limiting Middleware
# ============================================================================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to rate limit requests
    
    Usage in main.py:
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=60
        )
    """
    
    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 60,
        by_ip: bool = True
    ):
        super().__init__(app)
        self.rate_limiter = RateLimiter(requests_per_minute)
        self.by_ip = by_ip
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process each request"""
        
        # Get client identifier
        if self.by_ip:
            client_id = request.client.host if request.client else "unknown"
        else:
            # Use API key or user ID from headers
            client_id = request.headers.get("X-API-Key") or \
                       request.headers.get("X-User-ID") or \
                       request.client.host if request.client else "unknown"
        
        # Check rate limit
        if not self.rate_limiter.is_allowed(client_id):
            retry_after = self.rate_limiter.get_retry_after(client_id)
            
            logger.warning(f"Rate limit exceeded for {client_id}")
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Try again in {retry_after:.1f} seconds",
                    "retry_after": retry_after
                },
                headers={
                    "Retry-After": str(int(retry_after) + 1)
                }
            )
        
        # Process request normally
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.rate_limiter.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = "1"  # Simplified
        
        return response


# ============================================================================
# Request ID Middleware
# ============================================================================

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Add unique request ID to each request
    
    Useful for:
    - Request tracing
    - Log correlation
    - Debugging
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add request ID"""
        
        # Generate or use existing request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        
        # Store in request state
        request.state.request_id = request_id
        
        # Process request
        response = await call_next(request)
        
        # Add to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response


# ============================================================================
# Authentication Middleware (JWT)
# ============================================================================

class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    JWT Authentication Middleware
    
    Checks for valid JWT token in Authorization header
    """
    
    def __init__(
        self,
        app: ASGIApp,
        secret_key: str = "your-secret-key",
        excluded_paths: list = None
    ):
        super().__init__(app)
        self.secret_key = secret_key
        self.excluded_paths = excluded_paths or [
            "/", "/health", "/ready", "/docs", "/redoc", "/openapi.json"
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check authentication"""
        
        # Skip authentication for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        # Check for Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "message": "Missing Authorization header"
                },
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Validate token format
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "message": "Invalid Authorization header format"
                }
            )
        
        token = auth_header.replace("Bearer ", "")
        
        # Validate JWT token
        user = self._verify_token(token)
        
        if not user:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "message": "Invalid or expired token"
                }
            )
        
        # Store user in request state
        request.state.user = user
        
        # Process request
        response = await call_next(request)
        
        return response
    
    def _verify_token(self, token: str) -> Optional[Dict]:
        """
        Verify JWT token
        
        TODO: Implement actual JWT verification using python-jose
        """
        try:
            # Placeholder - implement actual JWT verification
            # from jose import jwt
            # payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            # return payload
            
            # For now, accept any token (DEVELOPMENT ONLY!)
            return {"user_id": "test-user", "role": "admin"}
            
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            return None


# ============================================================================
# Logging Middleware
# ============================================================================

class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Detailed request/response logging
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response"""
        
        # Get request ID
        request_id = getattr(request.state, "request_id", "unknown")
        
        # Log request
        logger.info(
            f"Request started | "
            f"ID: {request_id} | "
            f"Method: {request.method} | "
            f"Path: {request.url.path} | "
            f"Client: {request.client.host if request.client else 'unknown'}"
        )
        
        # Record start time
        start_time = time.time()
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log response
            logger.info(
                f"Request completed | "
                f"ID: {request_id} | "
                f"Status: {response.status_code} | "
                f"Duration: {duration:.4f}s"
            )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            
            logger.error(
                f"Request failed | "
                f"ID: {request_id} | "
                f"Error: {str(e)} | "
                f"Duration: {duration:.4f}s",
                exc_info=True
            )
            
            raise


# ============================================================================
# CORS Headers Middleware (Alternative to FastAPI CORS)
# ============================================================================

class CORSMiddleware(BaseHTTPMiddleware):
    """
    Custom CORS middleware
    
    Note: FastAPI already has built-in CORS, use that instead
    This is just an example
    """
    
    def __init__(
        self,
        app: ASGIApp,
        allow_origins: list = None,
        allow_methods: list = None,
        allow_headers: list = None
    ):
        super().__init__(app)
        self.allow_origins = allow_origins or ["*"]
        self.allow_methods = allow_methods or ["*"]
        self.allow_headers = allow_headers or ["*"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add CORS headers"""
        
        # Handle preflight requests
        if request.method == "OPTIONS":
            return Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": ", ".join(self.allow_methods),
                    "Access-Control-Allow-Headers": ", ".join(self.allow_headers),
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add CORS headers
        response.headers["Access-Control-Allow-Origin"] = "*"
        
        return response


# ============================================================================
# Decorator-based Rate Limiting
# ============================================================================

# Global rate limiter instance
global_rate_limiter = RateLimiter(requests_per_minute=60)


def rate_limit(requests_per_minute: int = 60):
    """
    Decorator for rate limiting specific endpoints
    
    Usage:
        @app.get("/api/resource")
        @rate_limit(requests_per_minute=10)
        async def my_endpoint():
            return {"data": "value"}
    """
    def decorator(func: Callable):
        limiter = RateLimiter(requests_per_minute)
        
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            client_id = request.client.host if request.client else "unknown"
            
            if not limiter.is_allowed(client_id):
                retry_after = limiter.get_retry_after(client_id)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Retry after {retry_after:.1f} seconds",
                    headers={"Retry-After": str(int(retry_after) + 1)}
                )
            
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator


# ============================================================================
# Helper Functions
# ============================================================================

def get_client_ip(request: Request) -> str:
    """
    Get client IP address from request
    Handles proxy headers (X-Forwarded-For, X-Real-IP)
    """
    # Check proxy headers
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback to direct client IP
    return request.client.host if request.client else "unknown"


def get_user_agent(request: Request) -> str:
    """Get user agent from request"""
    return request.headers.get("User-Agent", "unknown")


# ============================================================================
# Export all middleware
# ============================================================================

__all__ = [
    "RateLimitMiddleware",
    "RequestIDMiddleware",
    "AuthenticationMiddleware",
    "LoggingMiddleware",
    "CORSMiddleware",
    "rate_limit",
    "RateLimiter",
    "TokenBucket",
    "get_client_ip",
    "get_user_agent"
]
