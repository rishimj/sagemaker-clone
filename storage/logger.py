"""
Logging utility for ML Platform

Provides structured logging with context tracking for easier debugging.
"""
import logging
import json
import sys
from typing import Optional, Dict, Any
from datetime import datetime

class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add all extra fields from the record
        # These come from the 'extra' parameter in log calls
        # Exclude standard logging fields
        standard_fields = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName',
            'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'message', 'pathname', 'process', 'processName', 'relativeCreated',
            'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info',
            'getMessage', 'exc_info', 'exc_text', 'stack_info'
        }
        
        for key, value in record.__dict__.items():
            if key not in standard_fields:
                try:
                    # Try to JSON serialize the value
                    json.dumps(value)
                    log_data[key] = value
                except (TypeError, ValueError):
                    # If not serializable, convert to string
                    log_data[key] = str(value)
        
        return json.dumps(log_data)

class ContextAdapter(logging.LoggerAdapter):
    """Logger adapter that adds context to log records"""
    
    def process(self, msg, kwargs):
        """Add context to log record"""
        # Extract context from kwargs or use stored context
        extra = kwargs.setdefault('extra', {})
        
        if self.extra:
            # Merge stored context with any passed extra
            # Common fields are promoted to top level for easier filtering
            for key, value in self.extra.items():
                if key in ['job_id', 'request_id', 'task_arn', 'service', 'operation', 'table', 'bucket']:
                    # Promote common fields to top level (but don't override if already in extra)
                    if key not in extra:
                        extra[key] = value
                else:
                    # Other fields go into context sub-dict
                    if 'context' not in extra:
                        extra['context'] = {}
                    if key not in extra['context']:
                        extra['context'][key] = value
        
        return msg, kwargs

def setup_logger(
    name: str,
    level: str = 'INFO',
    use_json: bool = False,
    context: Optional[Dict[str, Any]] = None
) -> logging.Logger:
    """
    Setup logger with appropriate configuration
    
    Args:
        name: Logger name (usually __name__)
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        use_json: Whether to use JSON formatting (useful for Lambda/CloudWatch)
        context: Optional context dictionary to include in all logs
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Don't add handlers if they already exist
    if logger.handlers:
        return logger
    
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logger.level)
    
    # Set formatter
    if use_json:
        formatter = StructuredFormatter()
    else:
        # Human-readable formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Prevent propagation to root logger to avoid duplicate logs
    logger.propagate = False
    
    return logger

def get_logger(name: str, context: Optional[Dict[str, Any]] = None) -> ContextAdapter:
    """
    Get logger with context
    
    Args:
        name: Logger name (usually __name__)
        context: Optional context dictionary (job_id, request_id, etc.)
    
    Returns:
        ContextAdapter logger instance
    """
    # Determine if we should use JSON logging (typically for Lambda)
    use_json = 'LAMBDA_TASK_ROOT' in __import__('os').environ
    
    logger = setup_logger(name, use_json=use_json)
    
    if context:
        return ContextAdapter(logger, context)
    return ContextAdapter(logger, {})

# Convenience function for Lambda functions
def get_lambda_logger(context: Optional[Dict[str, Any]] = None) -> ContextAdapter:
    """
    Get logger configured for Lambda functions (with JSON output)
    
    Args:
        context: Optional context dictionary
    
    Returns:
        ContextAdapter logger instance
    """
    return get_logger('lambda', context)

