import logging
import os


def setup_logger(name):
    """
    Set up a logger with appropriate configuration for Lambda functions
    """
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger = logging.getLogger(name)

    # Clear any existing handlers to avoid duplicate logs
    if logger.handlers:
        logger.handlers.clear()

    # Configure logger
    logger.setLevel(getattr(logging, log_level))

    # Create console handler if not running in Lambda
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
