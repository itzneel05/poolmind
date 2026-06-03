"""poolmind — Cybersecurity Resource Pool"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

Path("data").mkdir(exist_ok=True)
Path("data/cache").mkdir(exist_ok=True)
