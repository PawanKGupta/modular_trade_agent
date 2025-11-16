import time
import threading
from enum import Enum
from typing import Callable, Any, Optional
from utils.logger import logger


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, calls fail fast
    HALF_OPEN = "half_open"  # Testing if service is back up


class CircuitBreaker:
    """
    Circuit breaker implementation to handle unreliable external services.
    
    States:
    - CLOSED: Normal operation, all calls go through
    - OPEN: Circuit is open, calls fail immediately without trying
    - HALF_OPEN: Limited calls allowed to test if service is back
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
        name: str = "CircuitBreaker"
    ):
        """
        Args:
            failure_threshold: Number of consecutive failures before opening circuit
            recovery_timeout: Time to wait before trying to close circuit again
            expected_exception: Exception type that should trigger circuit opening
            name: Name for logging purposes
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self._lock = threading.Lock()
        
        logger.info(f"Circuit breaker '{self.name}' initialized with threshold={failure_threshold}, timeout={recovery_timeout}s")
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator to wrap functions with circuit breaker logic."""
        def wrapper(*args, **kwargs):
            return self._call(func, *args, **kwargs)
        return wrapper
    
    def _call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker logic."""
        with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    logger.info(f"Circuit breaker '{self.name}' entering HALF_OPEN state")
                else:
                    logger.warning(f"Circuit breaker '{self.name}' is OPEN, failing fast")
                    raise Exception(f"Circuit breaker '{self.name}' is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        return (
            self.last_failure_time is not None and
            time.time() - self.last_failure_time >= self.recovery_timeout
        )
    
    def _on_success(self):
        """Handle successful call."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                logger.info(f"Circuit breaker '{self.name}' reset to CLOSED state")
            
            self.failure_count = 0
    
    def _on_failure(self):
        """Handle failed call."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit breaker '{self.name}' failed in HALF_OPEN, returning to OPEN state")
            elif self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.error(f"Circuit breaker '{self.name}' opened after {self.failure_count} failures")
    
    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        return self.state
    
    def reset(self):
        """Manually reset the circuit breaker."""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.last_failure_time = None
            logger.info(f"Circuit breaker '{self.name}' manually reset")


# Pre-configured circuit breakers for common use cases
def api_circuit_breaker(
    name: str = "API",
    failure_threshold: int = 3,
    recovery_timeout: float = 30.0
) -> CircuitBreaker:
    """Create a circuit breaker configured for API calls."""
    return CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        expected_exception=Exception,
        name=name
    )
