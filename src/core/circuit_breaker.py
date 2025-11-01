from datetime import datetime, timedelta
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"    # Normal operation
    OPEN = "open"        # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered

class CircuitBreaker:
    """Prevent cascade failures"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker"""
        
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
            
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Reset on success"""
        self.failures = 0
        self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        """Increment failures"""
        self.failures += 1
        self.last_failure_time = datetime.now()
        
        if self.failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(f"Circuit breaker OPENED after {self.failures} failures")
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time passed to retry"""
        if not self.last_failure_time:
            return True
        
        return (datetime.now() - self.last_failure_time).seconds >= self.timeout

# Usage
sap_circuit_breaker = CircuitBreaker(failure_threshold=3, timeout=60)

class BaseSAPModule:
    def call_bapi(self, bapi_name: str, **params) -> Dict:
        """Call BAPI with circuit breaker"""
        return sap_circuit_breaker.call(
            self._do_call_bapi,
            bapi_name,
            **params
        )