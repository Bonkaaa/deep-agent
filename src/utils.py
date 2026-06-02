import logging
from pathlib import Path

def setup_logger(log_file_name: str, logger_name: str, log_level=logging.INFO) -> logging.Logger:
    """
    Sets up a logger that writes to the specified file path.

    Args:
        log_file_name (str): The name of the log file.
        logger_name (str): The name of the logger.
        log_level: The logging level (default: logging.INFO).

    Returns:
        logging.Logger: Configured logger instance.
    """
    # Ensure the directory for the log file exists
    log_dir = Path(log_file_name).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create a logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)

    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Create a file handler
    file_handler = logging.FileHandler(logs_dir / log_file_name)
    file_handler.setLevel(log_level)

    # Create a formatter and set it for the handler
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)

    # Add the handler to the logger
    if not logger.hasHandlers():
        logger.addHandler(file_handler)

    return logger
    