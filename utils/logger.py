# utils/logger.py
import logging
import sys
from logging.handlers import RotatingFileHandler

def setup_logger(
    name: str = "streamlit_ai_app_gen",
    log_file: str = "app.log",
    level: int = logging.INFO,
    max_bytes: int = 10*1024*1024,  # 10 MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Configures and returns a logger instance with console and rotating file handlers.

    Args:
        name (str): The name of the logger.
        log_file (str): The name of the log file.
        level (int): The logging level (e.g., logging.INFO, logging.DEBUG).
        max_bytes (int): Maximum size of the log file before rotation.
        backup_count (int): Number of backup log files to keep.

    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)

    # Prevent adding multiple handlers if logger is already configured
    if logger.hasHandlers():
        logger.handlers.clear() # Clear existing handlers to reconfigure if needed

    logger.setLevel(level)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating File Handler
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.error(f"Failed to set up file handler for {log_file}: {e}", exc_info=True)
        # Continue without file logging if it fails

    # Set propagation to False to avoid duplicate logs if other loggers (e.g., root logger) are configured
    logger.propagate = False

    return logger

# Initialize a global logger instance for the application
app_logger = setup_logger()

if __name__ == "__main__":
    # Example usage:
    app_logger.debug("This is a debug message.")
    app_logger.info("This is an info message.")
    app_logger.warning("This is a warning message.")
    app_logger.error("This is an error message.")
    app_logger.critical("This is a critical message.")
