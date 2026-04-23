from pathlib import Path

# base path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOG_DIR = BASE_DIR / "logs"

#top processes limit 
PROCESS_LIMIT = 10