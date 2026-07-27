import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def hash_password(raw_password: str) -> bytes:
    """Simple salted hash for MVP purposes (swap for bcrypt/argon2 in production)."""
    salt = b"alabmart-static-salt"
    return hashlib.sha256(salt + raw_password.encode("utf-8")).digest()


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "alabmart.sqlite3"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash BLOB NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                items_json TEXT NOT NULL,
                total INTEGER NOT NULL,
                payment_method TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )


def create_user(email, password_hash):
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
            (email, password_hash, now_iso()),
        )
        return {"id": cursor.lastrowid, "email": email}


def find_user_by_email(email):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, email, password_hash, created_at FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    return dict(row) if row else None


def find_public_user(user_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def create_order(user_id, items, total, payment_method):
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO orders (user_id, items_json, total, payment_method, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, json.dumps(items), total, payment_method, "Paid - demo", now_iso()),
        )
        return {
            "id": cursor.lastrowid,
            "items": items,
            "total": total,
            "payment_method": payment_method,
            "status": "Paid - demo",
        }


def list_orders(user_id):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, items_json, total, payment_method, status, created_at
            FROM orders
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()

    orders = []
    for row in rows:
        order = dict(row)
        order["items"] = json.loads(order.pop("items_json"))
        orders.append(order)
    return orders
