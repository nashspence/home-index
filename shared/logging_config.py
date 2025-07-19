import logging
import logging.handlers
import os


files_logger = logging.getLogger("home-index-files")


def setup_logging() -> logging.Logger:
    """Configure debug hooks and file logging based on env vars."""
    if str(os.environ.get("DEBUG", "False")) == "True":
        import debugpy

        host = os.environ.get("DEBUGPY_HOST", "0.0.0.0")
        port = int(os.environ.get("DEBUGPY_PORT", 5678))
        debugpy.listen((host, port))
        if str(os.environ.get("WAIT_FOR_DEBUGPY_CLIENT", "False")) == "True":
            print("Waiting for debugger to attach...")
            debugpy.wait_for_client()
            print("Debugger attached.")
            debugpy.breakpoint()

    level = os.environ.get("LOGGING_LEVEL", "INFO")
    max_bytes = int(os.environ.get("LOGGING_MAX_BYTES", 5_000_000))
    backup_count = int(os.environ.get("LOGGING_BACKUP_COUNT", 10))
    logging.basicConfig(
        level=logging.CRITICAL,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    directory = os.environ.get("LOGGING_DIRECTORY", "/home-index")
    os.makedirs(directory, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        os.path.join(directory, "files.log"),
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    files_logger.setLevel(level)
    files_logger.addHandler(handler)
    return files_logger
