import sqlite3
import threading
from src.config.config import DB_PATH
from src.logger.logger import Logger

logger = Logger.setup_logs()

# Tables:
# 1. user - Stores user details
# 2. network_metrics - Stores network upload/download statistics
# 3. process_metrics - Stores top running system processes per user
# 4. system_metrics -  Stores CPU, memory, battery and system health data
# 5. settings -  Key-value store for application configuration

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT UNIQUE NOT NULL,
password_hash TEXT NOT NULL,
email TEXT DEFAULT '',
is_admin INTEGER DEFAULT 0,
created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS network_metrics (
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT NOT NULL,
timestamp TEXT NOT NULL,
upload_speed_mb  REAL,
download_speed_mb REAL,
bytes_sent INTEGER,
bytes_received INTEGER
);

CREATE TABLE IF NOT EXISTS process_metrics (
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT NOT NULL,
timestamp TEXT NOT NULL,
process_name TEXT,
cpu_percent REAL,
memory_percent REAL
);

CREATE TABLE IF NOT EXISTS system_metrics (
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT NOT NULL,
timestamp TEXT NOT NULL,
overall_cpu_load REAL,
vm_total_memory REAL,
vm_available_memory REAL,
vm_used_memory REAL,
vm_percent_used REAL,
swap_memory_available_total REAL,
swap_memory_used REAL,
battery_percent REAL
);

CREATE TABLE IF NOT EXISTS settings (
key TEXT PRIMARY KEY,
value TEXT NOT NULL
);

-- default admin settings
INSERT OR IGNORE INTO settings (key, value) VALUES
('max_monitor_minutes', '5'),
('app_name', 'System Performance Analyzer'),
('allow_registration', '1');
"""

# Store thread-specific database connections
_local = threading.local()
# why use thread here ?
# If we have 2 users one is log in request another is using dashboard request here thread will help to process request simultaneously. without threads, requests wait one by one


def get_conn() -> sqlite3.Connection:
    """
    Get a thread-local SQLite database connection.

    This function returns a database connection specific to the current thread. If no connection exists for the thread, a new one is created and configured. Subsequent calls within the same thread reuse the existing connection

     Connection Configuration:
        - Uses SQLite database file defined by DB_PATH.
        - Enables row access by column name via sqlite3.Row.
        - Enables WAL (Write-Ahead Logging) mode for improved concurrency.
        - Enables foreign key constraint enforcement.

    Thread Behavior:
        - First call in a thread creates a new connection.
        - Later calls in the same thread reuse that connection.
        - Different threads receive separate connections.

    Returns:
        sqlite3.Connection:
            Active SQLite connection for the current thread.

    Example:
        conn = get_conn()
        rows = conn.execute("SELECT * FROM users").fetchall()
    """
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL;")
        _local.conn.execute("PRAGMA foreign_keys=ON;")
    return _local.conn


def init_db():
    """
    Initialize the SQLite database schema. Creates all tables, indexes, and default settings if they do not already exist. Should be called once during application startup.
    """
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    logger.info("Database initialised.")


# Users
def insert_user(username, password_hash, email, is_admin=0) -> bool:
    """
    Insert a new user.
    """
    try:
        get_conn().execute(
            "INSERT INTO users (username,password_hash,email,is_admin) VALUES (?,?,?,?)",
            (username, password_hash, email, is_admin),
        )
        get_conn().commit()
        return True
    except sqlite3.IntegrityError:
        return False


def get_user(username):
    return (
        get_conn()
        .execute("SELECT * FROM users WHERE username=?", (username,))
        .fetchone()
    )


def update_password(username, new_hash):
    get_conn().execute(
        "UPDATE users SET password_hash=? WHERE username=?", (new_hash, username)
    )
    get_conn().commit()


def all_users():
    rows = (
        get_conn()
        .execute(
            "SELECT id,username,email,is_admin,created_at FROM users ORDER BY created_at DESC"
        )
        .fetchall()
    )
    return [dict(r) for r in rows]


def delete_user(username):
    c = get_conn()
    for tbl in ("system_metrics", "process_metrics", "network_metrics"):
        c.execute(f"DELETE FROM {tbl} WHERE username=?", (username,))
    c.execute("DELETE FROM users WHERE username=?", (username,))
    c.commit()


# Metric inserts
def insert_network_metric(username: str, data: dict):
    get_conn().execute(
        """
        INSERT INTO network_metrics
          (username,timestamp,upload_speed_mb,download_speed_mb,bytes_sent,bytes_received)
        VALUES (?,?,?,?,?,?)
    """,
        (
            username,
            data.get("timestamp"),
            data.get("upload_speed_mb"),
            data.get("download_speed_mb"),
            data.get("bytes_sent"),
            data.get("bytes_received"),
        ),
    )
    get_conn().commit()


def insert_process_metrics(username: str, timestamp: str, processes: list):
    rows = [
        (
            username,
            timestamp,
            p.get("name"),
            p.get("cpu_percent"),
            p.get("memory_percent"),
        )
        for p in processes
    ]
    get_conn().executemany(
        "INSERT INTO process_metrics (username,timestamp,process_name,cpu_percent,memory_percent) VALUES (?,?,?,?,?)",
        rows,
    )
    get_conn().commit()


def insert_system_metric(username: str, data: dict):
    get_conn().execute(
        """
        INSERT INTO system_metrics
          (username,timestamp,overall_cpu_load,vm_total_memory,vm_available_memory,
           vm_used_memory,vm_percent_used,swap_memory_available_total,swap_memory_used,battery_percent)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """,
        (
            username,
            data.get("timestamp"),
            data.get("cpu_metrics", {}).get("overall_cpu_load"),
            data.get("memory_metrics", {}).get("vm_total_memory"),
            data.get("memory_metrics", {}).get("vm_available_memory"),
            data.get("memory_metrics", {}).get("vm_used_memory"),
            data.get("memory_metrics", {}).get("vm_percent_used"),
            data.get("memory_metrics", {}).get("swap_memory_available_total"),
            data.get("memory_metrics", {}).get("swap_memory_used"),
            data.get("battery_metrics", {}).get("current_battery_percent"),
        ),
    )
    get_conn().commit()


# fetches Metrics
def fetch_network_metrics(username: str, day: int = None):
    if day:
        rows = (
            get_conn()
            .execute(
                "SELECT * FROM network_metrics WHERE username=? AND CAST(strftime('%d',timestamp) AS INTEGER)=? ORDER BY timestamp",
                (username, day),
            )
            .fetchall()
        )
    else:
        rows = (
            get_conn()
            .execute(
                "SELECT * FROM network_metrics WHERE username=? ORDER BY timestamp",
                (username,),
            )
            .fetchall()
        )
    return [dict(r) for r in rows]


def fetch_process_metrics(username: str, day: int = None):
    if day:
        rows = (
            get_conn()
            .execute(
                "SELECT * FROM process_metrics WHERE username=? AND CAST(strftime('%d',timestamp) AS INTEGER)=? ORDER BY timestamp",
                (username, day),
            )
            .fetchall()
        )
    else:
        rows = (
            get_conn()
            .execute(
                "SELECT * FROM process_metrics WHERE username=? ORDER BY timestamp",
                (username,),
            )
            .fetchall()
        )
    return [dict(r) for r in rows]


def fetch_system_metrics(username: str, day: int = None):
    if day:
        rows = (
            get_conn()
            .execute(
                "SELECT * FROM system_metrics WHERE username=? AND CAST(strftime('%d',timestamp) AS INTEGER)=? ORDER BY timestamp",
                (username, day),
            )
            .fetchall()
        )
    else:
        rows = (
            get_conn()
            .execute(
                "SELECT * FROM system_metrics WHERE username=? ORDER BY timestamp",
                (username,),
            )
            .fetchall()
        )
    return [dict(r) for r in rows]


def available_days(username: str):
    rows = (
        get_conn()
        .execute(
            "SELECT DISTINCT CAST(strftime('%d',timestamp) AS INTEGER) d FROM system_metrics WHERE username=? ORDER BY d",
            (username,),
        )
        .fetchall()
    )
    return [r["d"] for r in rows]


def user_stats(username: str) -> dict:
    c = get_conn()
    return {
        "system_rows": c.execute(
            "SELECT COUNT(*) FROM system_metrics  WHERE username=?", (username,)
        ).fetchone()[0],
        "process_rows": c.execute(
            "SELECT COUNT(*) FROM process_metrics WHERE username=?", (username,)
        ).fetchone()[0],
        "network_rows": c.execute(
            "SELECT COUNT(*) FROM network_metrics WHERE username=?", (username,)
        ).fetchone()[0],
    }


def db_size_kb() -> float:
    return round(DB_PATH.stat().st_size / 1024, 1) if DB_PATH.exists() else 0.0


def global_stats() -> dict:
    c = get_conn()
    return {
        "total_users": c.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "system_rows": c.execute("SELECT COUNT(*) FROM system_metrics").fetchone()[0],
        "process_rows": c.execute("SELECT COUNT(*) FROM process_metrics").fetchone()[0],
        "network_rows": c.execute("SELECT COUNT(*) FROM network_metrics").fetchone()[0],
        "db_size_kb": db_size_kb(),
    }
