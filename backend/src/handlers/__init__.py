"""Lambda entry points. Each module exposes ``handler(event, context)``."""
import logging
import os

logging.getLogger().setLevel(os.environ.get("LOG_LEVEL", "INFO"))
