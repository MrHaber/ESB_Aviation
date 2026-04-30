from loguru import logger
from ..core.config import settings
import os

def setup_logging():
    log_file = os.path.join(settings.LOG_DIR, "rotating_log.log")
    os.makedirs(settings.LOG_DIR, exist_ok=True)
    logger.add(log_file, rotation="1 week", format="{time} {level} {message}", enqueue=False)
