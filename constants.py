# constants.py
import os

APP_VERSION = "RCOE-Carpool-v2-modular-2025-08-22"

APP_SECRET = os.environ.get("APP_SECRET", "dev-secret-change-me")
# Default DB is now data.db (can be overridden by env var)
DATABASE_URL = os.environ.get("DATABASE_URL", os.path.abspath("data.db"))

MEMBERS = {"CA": "Christian", "ER": "Eric", "SJ": "Sean"}
MEMBER_ORDER = ["CA", "ER", "SJ"]
ROLE_CHOICES = {"D", "R", "O"}
MILES_PER_RIDE = 36
GAS_PRICE = 4.78
AVG_MPG = 22.0
