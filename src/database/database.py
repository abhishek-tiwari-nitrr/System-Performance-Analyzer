import os
import sqlite3
import threading
from src.config.config import DB_PATH, DATA_DIR
from src.logger.logger import logger


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
    os.makedirs(DATA_DIR, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
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

    Args:
        username(str): Unique username
        password_hash(str): Hashed password
        email(str): User email
        is_admin(int): 1 if admin, else 0

    Returns:
        bool: True if inserted, False if username exists
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
    """
    Fetch a user by username.

    Args: username(str)

    Returns:
        sqlite3.Row | None: User record or None if not found
    """
    return (
        get_conn()
        .execute("SELECT * FROM users WHERE username=?", (username,))
        .fetchone()
    )


def update_password(username, new_hash):
    """
    Update the Users Password.

    Args:
        username(str): Unique username
        password_hash(str): Hashed password
    """
    get_conn().execute(
        "UPDATE users SET password_hash=? WHERE username=?", (new_hash, username)
    )
    get_conn().commit()


def all_users():
    """
    Retrieve all users in the system.

    Users are returned in descending order of creation time (most recently created users first)

    Return:
        list:
            Retrieve all user records sorted by date in descending order
    """
    rows = (
        get_conn()
        .execute(
            "SELECT id,username,email,is_admin,created_at FROM users ORDER BY created_at DESC"
        )
        .fetchall()
    )
    return [dict(r) for r in rows]


def delete_user(username):
    """
    Delete a user from the database.

    This operation will also delete all related records (system, process, and network metrics) automatically

    Args:
        username(str): Unique username
    """
    c = get_conn()
    for tbl in ("system_metrics", "process_metrics", "network_metrics"):
        c.execute(f"DELETE FROM {tbl} WHERE username=?", (username,))
    c.execute("DELETE FROM users WHERE username=?", (username,))
    c.commit()


# Metric inserts
def insert_network_metric(username: str, data: dict):
    """
    Insert network performance metrics for a user.

    Args:
        username(str): Unique username
        data(dict):
            - upload_speed_mb(float)
            - download_speed_mb(float)
            - bytes_sent(int)
            - bytes_received(int)
            - timestamp(str)
    """
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
    """
    Insert multiple process metrics for a user.

    Args:
        - username(str): Unique username
        - timestamp(str): Date time
        - processes(list):
            - name(str)
            - cpu_percent(float)
            - memory_percent(float)
    """
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
    """
    Insert multiple system metrics for a user.

     Args:
        - username(str): Unique username
        - data(dict):
            - timestamp(str)
            - cpu_metrics(dict):
                - overall_cpu_load(float)
            - memory_metrics(dict):
                - vm_total_memory(float)
                - vm_available_memory(float)
                - vm_used_memory(float)
                - vm_percent_used(float)
                - swap_memory_available_total(float)
                - swap_memory_used(float)
            - battery_metrics(dict):
                - current_battery_percent(float)
    """
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
            data.get("overall_cpu_load"),
            data.get("vm_total_memory"),
            data.get("vm_available_memory"),
            data.get("vm_used_memory"),
            data.get("vm_percent_used"),
            data.get("swap_memory_available_total"),
            data.get("swap_memory_used"),
            data.get("current_battery_percent"),
        ),
    )
    get_conn().commit()


# fetches Metrics
def fetch_network_metrics(username: str, date: str = None):
    """
    Fetch network metrics for a user.

    Args:
        - username(str): Unique username
        - date(str): date filter
    Return:
        list:
            List of network metric records ordered by timestamp
    """
    if date is not None:
        rows = (
            get_conn()
            .execute(
                "SELECT * FROM network_metrics WHERE username=? AND DATE(timestamp)=DATE(?) ORDER BY timestamp",
                (username, date),
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


def fetch_process_metrics(username: str, date: str = None):
    """
    Fetch process metrics for a user.

    Args:
        - username(str): Unique username
        - date(str): date filter
    Return:
        list:
            List of process metric records ordered by timestamp
    """
    if date is not None:
        rows = (
            get_conn()
            .execute(
                "SELECT * FROM process_metrics WHERE username=? AND DATE(timestamp)=DATE(?) ORDER BY timestamp",
                (username, date),
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


def fetch_system_metrics(username: str, date: str = None):
    """
    Fetch system metrics for a user.

    Args:
        - username(str): Unique username
        - date(str): date filter
    Return:
        list:
            List of system metric records ordered by timestamp
    """
    if date is not None:
        rows = (
            get_conn()
            .execute(
                "SELECT * FROM system_metrics WHERE username=? AND DATE(timestamp)=DATE(?) ORDER BY timestamp",
                (username, date),
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
    """
    Get all distinct dates for which system metrics exist for a user.

    Args:
        - username(str): Unique username
    Return:
        list:
            List of dates in ascending order
    """
    rows = (
        get_conn()
        .execute(
            "SELECT DISTINCT DATE(timestamp) d FROM system_metrics WHERE username=? ORDER BY d",
            (username,),
        )
        .fetchall()
    )
    return [r["d"] for r in rows]


def user_stats(username: str) -> dict:
    """
    Get total metric row counts for a specific user.

    This provides a quick overview of how much data has been collected per category

    Args:
        - username(str): Unique username

    Return:
        dict:
            dictionary containing for user:
                - system_rows(int): count
                - process_rows(int): count
                - network_rows(int): count
    """
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
    """
    Get the current SQLite database file size in kilobytes.

    Returns:
        float:
            Size of the database file in KB. Returns 0.0 if the file does not exist
    """
    return round(DB_PATH.stat().st_size / 1024, 1) if DB_PATH.exists() else 0.0


def global_stats() -> dict:
    """
    Get overall database statistics.

    Returns:
        dict:
            A dictionary containing:
            - total_users(int)
            - system_rows(int)
            - process_rows(int)
            - network_rows(int)
            - db_size_kb(float)
    """
    c = get_conn()
    return {
        "total_users": c.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "system_rows": c.execute("SELECT COUNT(*) FROM system_metrics").fetchone()[0],
        "process_rows": c.execute("SELECT COUNT(*) FROM process_metrics").fetchone()[0],
        "network_rows": c.execute("SELECT COUNT(*) FROM network_metrics").fetchone()[0],
        "db_size_kb": db_size_kb(),
    }


# settings
def get_setting(key: str, default=None):
    """
    Retrieve a setting value by key from the database.

     Args:
        key(str): The setting key to look up
        default(Any, optional): Value to return if the key is not found. Defaults to None
    Return:
        - str: The stored value as a string if found, otherwise the provided default
    """
    row = (
        get_conn().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    )
    return row["value"] if row else default


def set_setting(key: str, value: str):
    """
    Insert or update a setting in the database.

    Args:
        key(str): The setting key to look up
        value(str): The value to store (will be converted to string)
    """
    get_conn().execute(
        "INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)",
        (key, str(value)),
    )
    get_conn().commit()


def all_settings() -> dict:
    """
    Retrieve all settings from the database.

    Return:
        dict:
            Lists of All key and values
    """
    rows = get_conn().execute("SELECT key,value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}
