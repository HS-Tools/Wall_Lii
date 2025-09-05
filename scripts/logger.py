import logging
import os


def setup_logger(name):
    """Setup logger with consistent format across all components"""
    logger = logging.getLogger(name)

    # Set level based on environment
    level = os.environ.get("LOG_LEVEL", "INFO")
    logger.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Add handler if none exists
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
