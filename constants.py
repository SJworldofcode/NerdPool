# constants.py
import os
APP_VERSION = "NerdPool_9_2025"
APP_SECRET  = os.environ.get("APP_SECRET", "dev-secret-change-me")
DATABASE_URL = os.path.abspath("np_data.db") 
ROLE_CHOICES = {"D","R","O"}

# TEMPORARY fallback for legacy routes still expecting these
MEMBERS = {"CA": "Christian", "ER": "Eric", "SJ": "Sean"}
MEMBER_ORDER = ["CA", "ER", "SJ"]