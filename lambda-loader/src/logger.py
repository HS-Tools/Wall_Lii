import logging


def setup_logger(name):
    """Setup logger with consistent format across all components"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Create console handler with formatting
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
