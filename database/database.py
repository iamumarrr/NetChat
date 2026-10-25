import hashlib
import hmac
import os
import sqlite3
from datetime import datetime
from pathlib import Path


# Always use the database located beside this Python file.
# This prevents accidentally creating a different database when
# the server is launched from another working directory.
DATABASE_FILE = Path(__file__).resolve().parent / "netchat.db"

HASH_ALGORITHM = "sha256"
ITERATIONS = 600_000
SALT_SIZE = 16
KEY_LENGTH = 32


def get_connection():
    """Create a connection to the persistent SQLite database."""
    DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        str(DATABASE_FILE),
        timeout=10
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def current_timestamp():
    """Return a timestamp with the local timezone."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


# --------------------------------------------------
# DATABASE INITIALIZATION
# --------------------------------------------------

def initialize_database():
    """Create tables if they do not already exist."""
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT NOT NULL,
                recipient TEXT,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_name TEXT NOT NULL,
                sender TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Persisted memberships survive logouts and server restarts.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_memberships (
                group_name TEXT NOT NULL COLLATE NOCASE,
                username TEXT NOT NULL,
                joined_at TEXT NOT NULL,
                PRIMARY KEY (group_name, username)
            )
        """)

        # Indexes help the history queries remain efficient.
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_public
            ON messages(recipient, id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_private
            ON messages(sender, recipient, id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_messages
            ON group_messages(group_name, id)
        """)

        connection.commit()

    finally:
        connection.close()


# --------------------------------------------------
# USER AUTHENTICATION
# --------------------------------------------------

def _hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        HASH_ALGORITHM,
        password.encode("utf-8"),
        salt,
        ITERATIONS,
        dklen=KEY_LENGTH
    )


def register_user(username, password):
    """Register a new user. Returns (success, message)."""
    if not isinstance(username, str) or not isinstance(password, str):
        return False, "Username and password must be text."

    username = username.strip()

    if len(username) < 3:
        return False, "Username must contain at least 3 characters."

    if len(username) > 32:
        return False, "Username cannot exceed 32 characters."

    if not username.replace("_", "").replace("-", "").isalnum():
        return False, "Username may contain letters, numbers, '_' and '-'."

    if len(password) < 6:
        return False, "Password must contain at least 6 characters."

    salt = os.urandom(SALT_SIZE)
    password_hash = _hash_password(password, salt).hex()

    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO users
                (username, password_hash, salt, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                username,
                password_hash,
                salt.hex(),
                current_timestamp()
            )
        )

        connection.commit()
        return True, "Registration successful."

    except sqlite3.IntegrityError:
        return False, "Registration could not be completed."

    finally:
        connection.close()


def authenticate_user(username, password):
    """Verify a username and password."""
    if not isinstance(username, str) or not isinstance(password, str):
        return False

    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT password_hash, salt
            FROM users
            WHERE username = ?
            """,
            (username.strip(),)
        ).fetchone()

        if row is None:
            return False

        try:
            salt = bytes.fromhex(row["salt"])
            expected_hash = bytes.fromhex(row["password_hash"])
        except (TypeError, ValueError):
            return False

        actual_hash = _hash_password(password, salt)

        return hmac.compare_digest(
            actual_hash,
            expected_hash
        )

    finally:
        connection.close()


# --------------------------------------------------
# PUBLIC MESSAGES
# --------------------------------------------------

def save_public_message(sender, message):
    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO messages
                (sender, recipient, message, created_at)
            VALUES (?, NULL, ?, ?)
            """,
            (sender, message, current_timestamp())
        )

        connection.commit()

    finally:
        connection.close()


def get_public_history(limit=50):
    """Return public messages in chronological order."""
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT sender, message, created_at
            FROM messages
            WHERE recipient IS NULL
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, int(limit)),)
        ).fetchall()

        return [dict(row) for row in reversed(rows)]

    finally:
        connection.close()


# --------------------------------------------------
# PRIVATE MESSAGES
# --------------------------------------------------

def save_private_message(sender, recipient, message):
    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO messages
                (sender, recipient, message, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (sender, recipient, message, current_timestamp())
        )

        connection.commit()

    finally:
        connection.close()


def get_private_history(username, other_user, limit=50):
    """Return messages exchanged between two users."""
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT sender, recipient, message, created_at
            FROM messages
            WHERE recipient IS NOT NULL
              AND (
                    (sender = ? AND recipient = ?)
                 OR (sender = ? AND recipient = ?)
              )
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                username,
                other_user,
                other_user,
                username,
                max(1, int(limit))
            )
        ).fetchall()

        return [dict(row) for row in reversed(rows)]

    finally:
        connection.close()


# --------------------------------------------------
# GROUPS
# --------------------------------------------------

def create_group(group_name, created_by):
    """Create a group. Returns (success, group name or error)."""
    if not isinstance(group_name, str):
        return False, "Invalid group name."

    group_name = group_name.strip().lower()

    if not group_name:
        return False, "Group name is required."

    if len(group_name) > 50:
        return False, "Group name cannot exceed 50 characters."

    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO groups (name, created_by, created_at)
            VALUES (?, ?, ?)
            """,
            (group_name, created_by, current_timestamp())
        )

        connection.commit()
        return True, group_name

    except sqlite3.IntegrityError:
        return False, f"Group '{group_name}' already exists."

    finally:
        connection.close()


def get_groups():
    """Return all group names."""
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT name
            FROM groups
            ORDER BY name COLLATE NOCASE
            """
        ).fetchall()

        return [row["name"] for row in rows]

    finally:
        connection.close()


def group_exists(group_name):
    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT 1
            FROM groups
            WHERE name = ? COLLATE NOCASE
            """,
            (group_name.strip(),)
        ).fetchone()

        return row is not None

    finally:
        connection.close()


# --------------------------------------------------
# GROUP MESSAGES
# --------------------------------------------------

def save_group_message(group_name, sender, message):
    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO group_messages
                (group_name, sender, message, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                group_name.strip().lower(),
                sender,
                message,
                current_timestamp()
            )
        )

        connection.commit()

    finally:
        connection.close()


def get_group_history(group_name, limit=50):
    """Return group messages in chronological order."""
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT sender, message, created_at
            FROM group_messages
            WHERE group_name = ? COLLATE NOCASE
            ORDER BY id DESC
            LIMIT ?
            """,
            (group_name.strip(), max(1, int(limit)))
        ).fetchall()

        return [dict(row) for row in reversed(rows)]

    finally:
        connection.close()


# --------------------------------------------------
# PERSISTENT GROUP MEMBERSHIPS
# --------------------------------------------------

def add_group_membership(username, group_name):
    """Save a membership without creating duplicate records."""
    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT OR IGNORE INTO group_memberships
                (group_name, username, joined_at)
            VALUES (?, ?, ?)
            """,
            (
                group_name.strip().lower(),
                username,
                current_timestamp()
            )
        )

        connection.commit()

    finally:
        connection.close()


def remove_group_membership(username, group_name):
    """Delete membership only when the user explicitly leaves."""
    connection = get_connection()

    try:
        connection.execute(
            """
            DELETE FROM group_memberships
            WHERE username = ?
              AND group_name = ? COLLATE NOCASE
            """,
            (username, group_name.strip())
        )

        connection.commit()

    finally:
        connection.close()


def get_all_group_memberships():
    """Load all saved group memberships after server startup."""
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT group_name, username
            FROM group_memberships
            ORDER BY group_name COLLATE NOCASE,
                     username COLLATE NOCASE
            """
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


def get_user_groups(username):
    """Return the saved groups for one user."""
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT group_name
            FROM group_memberships
            WHERE username = ?
            ORDER BY group_name COLLATE NOCASE
            """,
            (username,)
        ).fetchall()

        return [row["group_name"] for row in rows]

    finally:
        connection.close()