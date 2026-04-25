from pathlib import Path

# base path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOG_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

# data base file path
DB_PATH = DATA_DIR / "spa.db"

# top processes limit 
PROCESS_LIMIT = 10

# network montior interval: in sec
NETWORK_MONITOR_INTERVAL = 5

# system metrics interval: in sec
SYSTEM_METRICS_INTERVAL = 5

# Max Montior Mins
MAX_MONITOR_MINUTES = 5

# user session
ALGORITHM  = "HS256"
TOKEN_DAYS = 7
TOKEN_PARAM = "session"